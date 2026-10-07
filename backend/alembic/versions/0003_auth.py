"""Account credentials and revocable sessions. Legacy personal data stays private."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('users',sa.Column('id',sa.String(),primary_key=True),sa.Column('email',sa.String(),nullable=False,unique=True),sa.Column('password_hash',sa.String(),nullable=False),sa.Column('profile',sa.JSON(),nullable=False))
    op.create_table('auth_sessions',sa.Column('token_hash',sa.String(),primary_key=True),sa.Column('user_id',sa.String(),sa.ForeignKey('users.id'),nullable=False),sa.Column('csrf',sa.String(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_auth_sessions_user_id','auth_sessions',['user_id'])

def downgrade():
    op.drop_table('auth_sessions')
    op.drop_table('users')
