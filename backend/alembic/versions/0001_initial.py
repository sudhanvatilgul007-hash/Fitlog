"""Initial fitlog schema, frozen independently from application models."""
from alembic import op
import sqlalchemy as sa
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('user_settings', sa.Column('id',sa.String(),primary_key=True),sa.Column('data',sa.JSON(),nullable=False))
    op.create_table('food_presets', sa.Column('id',sa.String(),primary_key=True),sa.Column('user_id',sa.String(),nullable=False),sa.Column('data',sa.JSON(),nullable=False))
    op.create_index('ix_food_presets_user_id','food_presets',['user_id'])
    op.create_table('daily_logs',
        sa.Column('id',sa.String(),primary_key=True),sa.Column('user_id',sa.String(),nullable=False),
        sa.Column('date',sa.String(),nullable=False),sa.Column('weight_kg',sa.Float(),nullable=False),
        sa.Column('profile',sa.String(),nullable=False),sa.Column('tdee',sa.Float(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('user_id','date'))
    op.create_index('ix_daily_logs_date','daily_logs',['date'])
    for name in ('food_entries','activity_entries'):
        op.create_table(name,sa.Column('id',sa.String(),primary_key=True),sa.Column('log_id',sa.String(),sa.ForeignKey('daily_logs.id'),nullable=False),sa.Column('data',sa.JSON(),nullable=False))
        op.create_index('ix_'+name+'_log_id',name,['log_id'])
    op.create_table('daily_analyses',
        sa.Column('id',sa.String(),primary_key=True),sa.Column('log_id',sa.String(),sa.ForeignKey('daily_logs.id'),nullable=False),
        sa.Column('snapshot_hash',sa.String(),nullable=False,unique=True),sa.Column('snapshot',sa.JSON(),nullable=False),
        sa.Column('status',sa.String(),nullable=False),sa.Column('response',sa.JSON(),nullable=True),
        sa.Column('provider',sa.String(),nullable=False),sa.Column('model',sa.String(),nullable=False),
        sa.Column('prompt_version',sa.String(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_daily_analyses_log_id','daily_analyses',['log_id'])

def downgrade():
    for name in ('daily_analyses','activity_entries','food_entries','daily_logs','food_presets','user_settings'):
        op.drop_table(name)
