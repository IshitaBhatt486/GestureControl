# GestureOS Architecture

## Design goals

GestureOS prioritizes fresh input over processing every frame, keeps blocking work
away from the UI, confines mutable recognition state to one worker, and isolates
OS side effects behind an action queue. The application is Windows-specific at its
camera backend, media-key, startup, packaging, and diagnostics boundaries.

## System context

```mermaid
flowchart LR
    User([User])
    Camera[(Webcam)]
    Mic[(Microphone)]
    Windows[(Windows media subsystem)]
    Files[(Settings and logs)]
    App[GestureOS]

    User -->|poses, swipes, pinch| Camera
    User -->|double clap| Mic
    Camera --> App
    Mic --> App
    App -->|media keys| Windows
    User <-->|dashboard, tray, settings| App
    App <-->|JSON settings / log output| Files
```

No network service or database is involved.

## Component architecture

```mermaid
flowchart TB
    Main[main.py] --> Settings[SettingsManager]
    Settings --> Startup[WindowsStartupManager]
    Main --> Window[MainWindow]
    Window --> Pages[Dashboard / DiagnosticsPage]
    Window --> Dialogs[Onboarding / SettingsDialog]
    Window --> Tray[System tray]
    Window --> Clap[ClapDetector]
    Window --> Manager[CameraManager]

    Manager --> Capture[CameraWorker]
    Manager --> Recognition[GestureWorker]
    Manager --> ActionWorker[ActionWorker]
    Capture --> Buffer[LatestFrameBuffer]
    Buffer --> Recognition

    Recognition --> Engine[GestureEngine]
    Engine --> Landmarks[HandLandmarkData]
    Recognition --> Filter[GestureFilter]
    Recognition --> Swipe[SwipeRecognizer]
    Recognition --> Pinch[PinchController]
    Recognition --> Mapper[ActionMapper]
    Mapper --> Queue[ActionQueue]
    Pinch --> Queue
    Queue --> ActionWorker
```

## Threading model

```mermaid
flowchart LR
    subgraph GUI[Qt GUI thread]
        UI[Widgets and image presentation]
        CM[CameraManager lifecycle]
    end

    subgraph CT[Capture QThread]
        Read[VideoCapture.read]
    end

    subgraph RT[Recognition QThread]
        Infer[MediaPipe inference]
        Recognize[Gesture/filter/motion logic]
    end

    subgraph AT[Action QThread]
        Execute[PyAutoGUI / keyboard calls]
    end

    subgraph Audio[PortAudio callback]
        Clap[Peak and RMS analysis]
    end

    Read -->|capacity 1| Latest[LatestFrameBuffer]
    Latest --> Infer --> Recognize
    Recognize -->|queued Qt signals| UI
    Recognize -->|non-blocking submit| Actions[ActionQueue]
    Actions --> Execute
    Clap -->|double_clap signal| UI
    UI --> CM
```

`threading.Event` requests capture and recognition shutdown. `LatestFrameBuffer`
uses a `Condition`; `ActionQueue` uses `queue.Queue`. Qt signals deliver results to
the main thread. Shutdown never waits synchronously in the GUI.

## Frame and gesture pipeline

```mermaid
flowchart TD
    Frame[BGR frame captured] --> Stamp[Attach capture time and camera FPS]
    Stamp --> Put{Buffer occupied?}
    Put -->|Yes| Drop[Count and replace stale frame]
    Put -->|No| Store[Store frame]
    Drop --> Store
    Store --> RGB[Convert BGR to RGB]
    RGB --> MP[MediaPipe Hands]
    MP --> Hand{Hand detected?}
    Hand -->|No| Unknown[Unknown result]
    Hand -->|Yes| Data[21-point HandLandmarkData]
    Data --> Static[Finger-angle static classifier]
    Data --> Swipe[Centroid swipe recognizer]
    Data --> Pinch[Pinch distance/motion controller]
    Static --> Filter[Rolling-majority persistence filter]
    Filter --> Arbitration{Pinch, then swipe, then static}
    Swipe --> Arbitration
    Pinch --> Arbitration
    Arbitration --> Map[JSON-configured ActionMapper]
    Map --> AQ[ActionQueue]
    AQ --> Keys[Windows media keys]
    Static --> Telemetry[Frame, confidence, activity, metrics]
    Telemetry --> UI[Dashboard and diagnostics]
```

## Action semantics

Static gestures must transition away before firing again. `ActionMapper` applies a
global cooldown. Swipes have independent motion and cooldown checks. Pinch volume
uses smoothed vertical movement and short step cooldowns. Every OS call is accepted
into a FIFO queue and executed on the action worker. Action errors are logged and
do not terminate recognition.

## Configuration and persistence

```mermaid
sequenceDiagram
    participant U as User
    participant D as SettingsDialog
    participant S as SettingsManager
    participant J as settings.json
    participant C as CameraManager

    U->>D: Edit sensitivity, binding, enabled state
    D->>S: update(validated values)
    S->>J: Write temporary JSON
    S->>J: Atomic replace
    S-->>D: Immutable AppSettings
    D->>C: update_settings(snapshot)
    Note over C: Applied when the next recognition session starts
```

Installed builds store settings under `%APPDATA%\GestureOS\config`. Source runs use
the repository configuration file. First-run onboarding state uses `QSettings`.

## Diagnostics

Capture timestamps travel with frames. The recognition worker calculates throughput
and capture-to-recognition latency, while `DiagnosticsMonitor` samples process CPU
and Windows working-set memory. `CameraManager` adds the number of live pipeline
threads before forwarding the immutable `PipelineMetrics` snapshot to the UI.

## Failure and shutdown behavior

- Camera and recognition exceptions emit one user-visible pipeline error.
- Worker `finally` blocks release camera and MediaPipe resources.
- Stopping closes the latest-frame buffer, allowing recognition to wake immediately.
- Recognition completion closes the action queue after all accepted commands.
- Each worker requests its event loop to quit; manager cleanup occurs after all
  three thread-finished signals.
- Application exit waits asynchronously for that terminal signal.

## Packaging architecture

PyInstaller creates a windowed single executable containing Python, Qt, MediaPipe,
OpenCV, assets, and native dependencies. NSIS installs it per-user, creates desktop
and Start Menu shortcuts, registers an uninstaller under HKCU, and supports `/S`.
