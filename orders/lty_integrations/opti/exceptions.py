class OptiServiceError(Exception):
    pass


class OptiAuthError(OptiServiceError):
    pass


class OptiRequestError(OptiServiceError):
    pass
