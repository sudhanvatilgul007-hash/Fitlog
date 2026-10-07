from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Settings(StrictModel):
    proteinMinG: float = Field(default=150, ge=0)
    proteinMaxG: float = Field(default=170, ge=0)
    deficitMinKcal: float = Field(default=800, ge=0)
    deficitMaxKcal: float = Field(default=1000, ge=0)
    walkingCoefficient: float = Field(default=0.5, gt=0, le=2)
    weightMinKg: float = Field(default=20, gt=0)
    weightMaxKg: float = Field(default=350, gt=0)
    tdeeProfiles: dict[str, float] = Field(default_factory=lambda: {'sedentary':2500, 'high_walking':3000, 'gym_walking':3250})
    @model_validator(mode='after')
    def ranges(self):
        if self.proteinMaxG < self.proteinMinG or self.deficitMaxKcal < self.deficitMinKcal or self.weightMaxKg <= self.weightMinKg:
            raise ValueError('Maximum must be greater than or equal to minimum')
        if not self.tdeeProfiles or any(not 500 <= n <= 10000 for n in self.tdeeProfiles.values()):
            raise ValueError('TDEE profiles must be between 500 and 10000 kcal')
        return self

class Food(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    baseQuantity: float = Field(default=1, gt=0)
    baseUnit: Literal['g','ml','scoop','slice','piece','serving','tbsp','tsp']
    calories: float = Field(ge=0)
    proteinG: float = Field(ge=0)
    carbsG: float | None = Field(default=None, ge=0)
    fatG: float | None = Field(default=None, ge=0)
    fiberG: float | None = Field(default=None, ge=0)
    favorite: bool = True
    sortOrder: int = 0
    active: bool = True

class FoodAdd(StrictModel):
    foodPresetId: str
    quantity: float = Field(gt=0, le=100000)
    unit: str
class FoodEdit(StrictModel):
    quantity: float = Field(gt=0, le=100000)
    unit: str
class Weight(StrictModel):
    weightKg: float = Field(gt=0)
class TDEE(StrictModel):
    profile: str
    kcal: float | None = Field(default=None, ge=500, le=10000)
class Activity(StrictModel):
    type: Literal['walking','cycling','treadmill','upper_body','pull','push','legs','abs','manual']
    distanceKm: float | None = Field(default=None, ge=0, le=300)
    durationMinutes: float | None = Field(default=None, gt=0, le=1440)
    steps: int | None = Field(default=None, ge=0)
    speedKmh: float | None = Field(default=None, gt=0, le=30)
    exerciseCount: int | None = Field(default=None, ge=1, le=100)
    caloriesEstimate: float | None = Field(default=None, ge=0, le=10000)
    @model_validator(mode='after')
    def required(self):
        if self.type=='walking' and not self.distanceKm:
            raise ValueError('Walking needs distance')
        if self.type in ('cycling','treadmill') and not self.durationMinutes:
            raise ValueError('Cardio needs duration')
        if self.type=='treadmill' and not self.speedKmh:
            raise ValueError('Treadmill needs speed')
        if self.type in ('upper_body','pull','push','legs','abs') and not self.exerciseCount:
            raise ValueError('Workout needs exercise count')
        if self.type=='manual' and self.caloriesEstimate is None:
            raise ValueError('Manual activity needs estimated calories')
        return self
class Analyze(StrictModel):
    confirmReanalysis: bool = False
    retry: bool = False
class AnalysisResponse(StrictModel):
    summary: str
    dayScore: int = Field(ge=1, le=10)
    proteinAssessment: str
    deficitAssessment: str
    activityAssessment: str
    warnings: list[str]
    recommendations: list[str]
    confidenceNotes: list[str]
