"""Public errors intentionally exclude provider bodies, keys and pasted text."""


class ServiceError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after = retry_after


class InvalidModelOutput(ServiceError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_model_output",
            "The model response did not pass validation. Your input and completed stages are saved; retry this stage later.",
        )
