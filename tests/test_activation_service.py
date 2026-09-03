from gestureos.services.activation_service import ActivationService


def test_activation_lifecycle(qtbot):
    service = ActivationService()
    changes = []
    service.changed.connect(changes.append)

    service.activate()
    service.activate()
    service.deactivate()

    assert changes == [True, False]
    assert service.is_active is False

