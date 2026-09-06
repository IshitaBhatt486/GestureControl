# Contributing to GestureOS

Thank you for improving GestureOS. Open an issue before large changes so the
approach can be agreed before implementation.

## Development workflow

1. Use Python 3.11 on Windows and create a virtual environment.
2. Install `gestureos/requirements.txt`.
3. Create a focused branch and keep unrelated changes separate.
4. Run `run_tests.cmd -q` before opening a pull request.
5. Include tests for behavior changes and update relevant documentation.

Pull requests must pass the 80% branch-coverage gate. Avoid network services in
the runtime path: local processing and user privacy are core product properties.

By contributing, you agree that your contribution is licensed under the MIT
License included in this repository.
