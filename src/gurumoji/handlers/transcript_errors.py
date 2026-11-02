"""文字起こしの同時編集で発生する競合。"""

class TranscriptConflictError(RuntimeError):
    def __init__(self, current_revision: int):
        super().__init__(
            "The transcript was changed by another editor. Reload before saving again."
        )
        self.current_revision = current_revision
