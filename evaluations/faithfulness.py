from ragas.metrics.collections import Faithfulness


class AuditedFaithfulness(Faithfulness):
    """保留忠实度评测中的逐条判断，便于人工复核。"""

    def __init__(self, llm):
        super().__init__(llm=llm)
        self.judgments = []

    async def _create_verdicts(
        self,
        statements: list[str],
        context: str,
    ):
        result = await super()._create_verdicts(
            statements,
            context,
        )

        self.judgments = result.model_dump(
            mode="json"
        )["statements"]

        return result