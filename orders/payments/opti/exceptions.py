class OptiError(Exception):
    pass


class OptiAuthError(OptiError):
    pass


class OptiOrderCreateError(OptiError):
    pass


class OptiQrError(OptiError):
    pass
