import hashlib
import json

def food_totals(entry):
    factor = entry['quantity'] / entry['nutrition']['baseQuantity']
    return {key: round(entry['nutrition'][key] * factor, 4) if entry['nutrition'].get(key) is not None else None
            for key in ('calories','proteinG','carbsG','fatG','fiberG')}

def activity_burn(activity, weight, coefficient, net=False):
    if activity['type'] == 'walking':
        return round(coefficient * weight * (activity.get('distanceKm') or 0), 2)
    if activity['type'] == 'manual':
        return activity.get('caloriesEstimate') or 0
    minutes = activity.get('durationMinutes') or 0
    if activity['type'] == 'treadmill':
        met = 1 + 0.1 * (activity['speedKmh'] * 1000 / 60) / 3.5
    else:
        met = 6 if activity['type'] == 'cycling' else 3.5
    return round(max(0, met - (1 if net else 0)) * 3.5 * weight / 200 * minutes, 2)

def snapshot(log, foods, activities, settings):
    food = [{**{k: e[k] for k in ('id','foodPresetId','displayName','quantity','unit','nutrition')}, **food_totals(e)} for e in sorted(foods,key=lambda x:x['id'])]
    config = log.expenditure_config or {'version':1, 'walkingCoefficient':settings['walkingCoefficient']}
    activity = [{**a, 'caloriesEstimate':activity_burn(a,log.weight_kg,config['walkingCoefficient'],net=config['version']>=2)} for a in sorted(activities,key=lambda x:x['id'])]
    walking = round(sum(a['caloriesEstimate'] for a in activity if a['type']=='walking'),2)
    exercise = round(sum(a['caloriesEstimate'] for a in activity if a['type']!='walking'),2)
    automatic = config['version']>=2 and log.profile=='automatic'
    baseline = round(log.tdee * log.weight_kg / config['referenceWeightKg'],2) if config['version']==2 and log.profile!='custom' else log.tdee
    resting = None
    factor = None
    if config['version']==3 and log.profile!='custom':
        resting = round(10*log.weight_kg + 6.25*config['heightCm'] - 5*config['age'] + (5 if config['gender']=='male' else -161),2)
        factor = config['activityFactors']['sedentary' if automatic else log.profile]
        baseline = round(resting*factor,2)
    expenditure = round(baseline + (walking + exercise if automatic else 0),2)
    incomplete = any(a['type'] in ('upper_body','pull','push','legs','abs') and not a.get('durationMinutes') for a in activity)
    calories = round(sum(f['calories'] for f in food),2)
    protein = round(sum(f['proteinG'] for f in food),2)
    calculated = {'totalCalories':calories,'totalProteinG':protein,'selectedTDEE':expenditure,'deficitKcal':round(expenditure-calories,2),
        'baselineExpenditureKcal':baseline,'totalExpenditureKcal':expenditure,
        'activityCaloriesEstimate':round(walking+exercise,2),'activityIncluded':automatic,
        'restingExpenditureKcal':resting,'activityFactor':factor,
        'expenditureMethod':'mifflin_st_jeor' if config['version']==3 and log.profile!='custom' else 'weight_activity' if automatic else 'weight_profile' if config['version']==2 and log.profile!='custom' else 'fixed',
        'expenditureEstimateIncomplete':incomplete,
        'referenceWeightKg':config.get('referenceWeightKg'),'referenceTDEEKcal':log.tdee,
        'walkingCaloriesEstimate':walking,
        'exerciseCaloriesEstimate':exercise}
    for k in ('carbsG','fatG','fiberG'):
        calculated[k] = round(sum(f[k] or 0 for f in food),2)
        calculated[k+'Complete'] = all(f[k] is not None for f in food)
    return {'userId':log.user_id,'date':log.date,'weightKg':log.weight_kg,'profile':log.profile,'targets':settings,'expenditureConfig':config,'food':food,'activity':activity,'calculated':calculated}

def snapshot_hash(data):
    # Database round-trips may turn integer-valued floats into ints or back.
    # Canonicalize all finite numbers so 2500 and 2500.0 represent the same input.
    def canonical(value):
        if isinstance(value, bool) or value is None: return value
        if isinstance(value, (int, float)): return float(value)
        if isinstance(value, dict): return {k:canonical(v) for k,v in value.items()}
        if isinstance(value, list): return [canonical(v) for v in value]
        return value
    return hashlib.sha256(json.dumps(canonical(data),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def averages(days):
    keys = ('weightKg','totalCalories','totalProteinG','selectedTDEE','deficitKcal')
    return {k:round(sum(d[k] for d in days)/len(days),2) if days else None for k in keys} | {'days':len(days)}
