import hashlib
import json

def food_totals(entry):
    factor = entry['quantity'] / entry['nutrition']['baseQuantity']
    return {key: round(entry['nutrition'][key] * factor, 4) if entry['nutrition'].get(key) is not None else None
            for key in ('calories','proteinG','carbsG','fatG','fiberG')}

def activity_burn(activity, weight, coefficient):
    if activity['type'] == 'walking':
        return round(coefficient * weight * (activity.get('distanceKm') or 0), 2)
    if activity['type'] == 'manual':
        return activity.get('caloriesEstimate') or 0
    minutes = activity.get('durationMinutes') or 0
    if activity['type'] == 'treadmill':
        met = 1 + 0.1 * (activity['speedKmh'] * 1000 / 60) / 3.5
    else:
        met = 6 if activity['type'] == 'cycling' else 3.5
    return round(met * 3.5 * weight / 200 * minutes, 2)

def snapshot(log, foods, activities, settings):
    food = [{**{k: e[k] for k in ('id','foodPresetId','displayName','quantity','unit','nutrition')}, **food_totals(e)} for e in sorted(foods,key=lambda x:x['id'])]
    activity = [{**a, 'caloriesEstimate':activity_burn(a,log.weight_kg,settings['walkingCoefficient'])} for a in sorted(activities,key=lambda x:x['id'])]
    calories = round(sum(f['calories'] for f in food),2)
    protein = round(sum(f['proteinG'] for f in food),2)
    calculated = {'totalCalories':calories,'totalProteinG':protein,'selectedTDEE':log.tdee,'deficitKcal':round(log.tdee-calories,2),
        'walkingCaloriesEstimate':round(sum(a['caloriesEstimate'] for a in activity if a['type']=='walking'),2),
        'exerciseCaloriesEstimate':round(sum(a['caloriesEstimate'] for a in activity if a['type']!='walking'),2)}
    for k in ('carbsG','fatG','fiberG'):
        calculated[k] = round(sum(f[k] or 0 for f in food),2)
        calculated[k+'Complete'] = all(f[k] is not None for f in food)
    return {'date':log.date,'weightKg':log.weight_kg,'profile':log.profile,'targets':settings,'food':food,'activity':activity,'calculated':calculated}

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
