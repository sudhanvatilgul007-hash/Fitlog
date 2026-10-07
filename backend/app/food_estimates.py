"""Saved-food reuse and one explicit provider request per nutrition estimate."""
import logging
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .models import FoodPreset, FoodNutritionEstimate
from .schemas import FoodEstimateRequest, FoodNutrition
from .calculations import snapshot_hash
from .provider import ProviderError

logger=logging.getLogger('fitlog.food_estimates')
NUTRIENTS=('calories','proteinG','carbsG','fatG')


def estimate_food(body: FoodEstimateRequest, db, provider_factory):
    # No fuzzy matches or implicit conversions: raw/cooked and g/ml differ.
    if not body.details:
        matches=[r for r in db.scalars(select(FoodPreset).where(FoodPreset.user_id==db.info['user_id']))
                 if r.data['active'] and ' '.join(r.data['name'].split()).casefold()==body.name.casefold()
                 and r.data['baseUnit']==body.baseUnit and all(r.data.get(k) is not None for k in NUTRIENTS)]
        # Multiple conflicting presets are ambiguous and require an estimate.
        scaled=[{k:round(r.data[k]*body.baseQuantity/r.data['baseQuantity'],2) for k in NUTRIENTS} for r in matches]
        if scaled and all(value==scaled[0] for value in scaled):
            row=matches[0]
            return {**scaled[0], 'fiberG':round(row.data['fiberG']*body.baseQuantity/row.data['baseQuantity'],2) if row.data.get('fiberG') is not None else None, 'source':'saved', 'notes':(f'Reused {row.data["name"]}, scaled to {body.baseQuantity:g} {body.baseUnit}. '+row.data.get('nutritionNotes',''))[:1000], 'cached':False}
    identity=body.model_dump(exclude={'retry'})
    identity['name']=identity['name'].casefold()
    identity['details']=identity['details'].casefold()
    key=snapshot_hash({'version':1,'user':db.info['user_id'],'food':identity})
    row=db.get(FoodNutritionEstimate,key)
    if row and row.status=='complete':return {**row.response,'cached':True}
    if row and row.status=='pending':raise HTTPException(409,'Nutrition estimate is in progress. Try again shortly; no extra AI call was made.')
    if row and not body.retry:raise HTTPException(409,'Previous estimate failed. Use Retry estimate to make another AI request.')
    try: provider=provider_factory()
    except ProviderError as exc:raise HTTPException(exc.status,str(exc)) from None
    if row:
        claim=db.execute(update(FoodNutritionEstimate).where(FoodNutritionEstimate.id==key,FoodNutritionEstimate.status=='failed').values(status='pending'))
        db.commit()
        if claim.rowcount!=1:raise HTTPException(409,'Nutrition estimate is already in progress.')
        db.refresh(row)
    else:
        row=FoodNutritionEstimate(id=key,user_id=db.info['user_id'],status='pending')
        db.add(row)
        try:db.commit()
        except IntegrityError:
            db.rollback();raise HTTPException(409,'Nutrition estimate is already in progress; no extra AI call was made.') from None
    try:
        nutrition=FoodNutrition.model_validate(provider.estimate_food(body.model_dump(exclude={'retry'}))).model_dump()
        row.response={**nutrition,'source':'ai'};row.status='complete';db.commit()
    except Exception as exc:
        db.rollback();db.refresh(row);row.status='failed';db.commit()
        if isinstance(exc,ProviderError):
            logger.warning('food_estimate_failed category=%s upstream_status=%s request_id=%s',exc.code,exc.upstream_status,exc.request_id)
            raise HTTPException(exc.status,str(exc)) from None
        logger.error('food_estimate_failed exception_type=%s',type(exc).__name__)
        raise HTTPException(502,'Nutrition estimate failed or returned invalid values. Enter label values manually, or explicitly retry.') from None
    return {**row.response,'cached':False}
