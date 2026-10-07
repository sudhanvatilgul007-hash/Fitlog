from .database import Session
from .models import UserSettings, FoodPreset
from .schemas import Settings, Food

def seed_user(db, user_id):
    if not db.get(UserSettings,user_id):
        db.add(UserSettings(id=user_id,data=Settings().model_dump()))
    seeds = [
        ('whey','Biozyme Whey',1,'scoop',140,25),
        ('amul','Amul Blueberry Protein',1,'serving',145,20),
        ('bread','High-protein bread',1,'slice',58,6.5),
        ('cheese','Cheese slice',1,'slice',60,4),
        ('pb','Pintola peanut butter',100,'g',639,30),
        ('soya','Soya chunks · dry',100,'g',345,52),
        ('chapathi','Chapathi',1,'piece',100,3),
        ('rice','Rice · cooked',100,'g',130,2.7),
        ('dal','Dal · cooked',100,'g',110,6),
        ('palak','Palak dal · cooked',100,'g',100,5),
        ('palya','Vegetable palya · cooked',100,'g',90,2)]
    for order,(id,name,base,unit,cal,protein) in enumerate(seeds):
        id = id if user_id=='personal' else user_id+':'+id
        if not db.get(FoodPreset,id):
            db.add(FoodPreset(id=id,user_id=user_id,data=Food(name=name,baseQuantity=base,baseUnit=unit,calories=cal,proteinG=protein,sortOrder=order).model_dump()))

def seed():
    with Session() as db:
        seed_user(db,'personal')
        db.commit()

if __name__ == '__main__':
    seed()
