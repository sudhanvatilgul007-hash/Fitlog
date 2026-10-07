"""Persist nutrition estimates to avoid duplicate paid requests."""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('food_nutrition_estimates',sa.Column('id',sa.String(),primary_key=True),sa.Column('user_id',sa.String(),nullable=False),sa.Column('status',sa.String(),nullable=False),sa.Column('response',sa.JSON(),nullable=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_food_nutrition_estimates_user_id','food_nutrition_estimates',['user_id'])

def downgrade():
    op.drop_table('food_nutrition_estimates')
