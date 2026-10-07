"""Administrator-only CLI to assign pre-authentication logs to a known account."""
import argparse
from sqlalchemy import select, update
from .database import Session
from .models import User, UserSettings, FoodPreset, DailyLog, FoodEntry, ActivityEntry, DailyAnalysis

def claim(db,email):
    user=db.scalar(select(User).where(User.email==email.strip().lower()))
    if not user: raise ValueError('Create the destination account first')
    logs=list(db.scalars(select(DailyLog).where(DailyLog.user_id==user.id)))
    for log in logs:
        if any(db.scalar(select(cls.id).where(cls.log_id==log.id).limit(1)) for cls in (FoodEntry,ActivityEntry,DailyAnalysis)):
            raise ValueError('Destination already has journal entries; merge requires administrator review')
    legacy=list(db.scalars(select(DailyLog).where(DailyLog.user_id=='personal')))
    if not legacy: raise ValueError('No legacy logs to transfer')
    for log in logs: db.delete(log)
    db.flush()
    for log in legacy: log.user_id=user.id
    # Keep both starter and edited legacy presets; legacy entry IDs remain valid.
    db.execute(update(FoodPreset).where(FoodPreset.user_id=='personal').values(user_id=user.id))
    old=db.get(UserSettings,'personal')
    if old: db.get(UserSettings,user.id).data=old.data.copy()
    db.commit()
    return len(legacy)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('email',help='Account whose ownership the administrator has verified')
    parser.add_argument('--confirm',action='store_true',required=True,help='Confirm assignment of legacy private data')
    args=parser.parse_args()
    with Session() as db:
        try: print(f'Transferred {claim(db,args.email)} legacy logs.')
        except ValueError as exc: parser.exit(1,str(exc)+'\n')
