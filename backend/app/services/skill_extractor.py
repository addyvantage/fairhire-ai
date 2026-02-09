import re

from app.services.interfaces import SkillExtractorInterface


class SkillExtractorService(SkillExtractorInterface):
    _known_skills = {
        "python",
        "java",
        "sql",
        "postgresql",
        "fastapi",
        "docker",
        "kubernetes",
        "aws",
        "gcp",
        "tensorflow",
        "pytorch",
        "react",
        "next.js",
        "nlp",
        "ml",
    }

    async def extract(self, text: str) -> list[str]:
        tokens = {token.lower() for token in re.findall(r"[a-zA-Z0-9.+#-]+", text)}
        matches = sorted(skill for skill in self._known_skills if skill in tokens)
        return matches
