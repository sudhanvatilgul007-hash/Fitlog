"""Store per-day expenditure calibration, preserving legacy historical totals."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('daily_logs',sa.Column('expenditure_config',sa.JSON(),nullable=True))
    conn=op.get_bind()
    settings=sa.table('user_settings',sa.column('data',sa.JSON()))
    data=conn.execute(sa.select(settings.c.data)).scalar() or {}
    logs=sa.table('daily_logs',sa.column('expenditure_config',sa.JSON()))
    conn.execute(logs.update().values(expenditure_config={'version':1,'walkingCoefficient':data.get('walkingCoefficient',.5)}))

def downgrade():
    op.drop_column('daily_logs','expenditure_config')
