from pydantic import BaseModel


class DashboardStatsOut(BaseModel):
    total_resumes: int
    analyses_run: int
    avg_match_score: float
