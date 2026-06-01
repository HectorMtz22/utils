class PxeBootError(Exception):
    exit_code: int = 1


class NeedsRoot(PxeBootError):
    exit_code = 77


class BrewMissing(PxeBootError):
    exit_code = 1


class NoNetwork(PxeBootError):
    exit_code = 1


class PortInUse(PxeBootError):
    exit_code = 1

    def __init__(self, port: int):
        super().__init__(f"port {port} already in use")
        self.port = port


class IsoNotFound(PxeBootError):
    exit_code = 1


class IsoInvalid(PxeBootError):
    exit_code = 1


class BootFilesNotFound(PxeBootError):
    exit_code = 1


class AlreadyRunning(PxeBootError):
    exit_code = 1
