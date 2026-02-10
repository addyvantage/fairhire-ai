from pydantic import BaseModel


class DashboardStatsOut(BaseModel):
    total_resumes: int
    total_analyses: int
    completed_analyses: int
    avg_match_score: float
    completion_rate: float
    total_job_profiles: int
