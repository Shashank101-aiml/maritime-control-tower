"""add voyage plans

Revision ID: c5e8a1d34f26
Revises: a3f1c9d27b40
Create Date: 2026-09-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5e8a1d34f26'
down_revision: Union[str, Sequence[str], None] = 'a3f1c9d27b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'voyage_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vessel_id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('destination_port', sa.String(length=80), nullable=True),
        sa.Column('scheduled_arrival', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['vessel_id'], ['fleet_vessels.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('voyage_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_voyage_plans_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_voyage_plans_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_voyage_plans_vessel_id'), ['vessel_id'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('voyage_plans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_voyage_plans_vessel_id'))
        batch_op.drop_index(batch_op.f('ix_voyage_plans_owner_id'))
        batch_op.drop_index(batch_op.f('ix_voyage_plans_id'))
    op.drop_table('voyage_plans')
