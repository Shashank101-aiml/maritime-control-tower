"""add fleet tables

Revision ID: a3f1c9d27b40
Revises: 570442c67e2b
Create Date: 2026-09-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f1c9d27b40'
down_revision: Union[str, Sequence[str], None] = '570442c67e2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fleet_vessels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('imo', sa.String(length=7), nullable=True),
        sa.Column('mmsi', sa.String(length=9), nullable=False),
        sa.Column('call_sign', sa.String(length=16), nullable=True),
        sa.Column('flag', sa.String(length=64), nullable=True),
        sa.Column('vessel_type', sa.String(length=30), nullable=False),
        sa.Column('monitoring_enabled', sa.Boolean(), nullable=False),
        sa.Column('ais_name', sa.String(length=128), nullable=True),
        sa.Column('ais_imo', sa.String(length=7), nullable=True),
        sa.Column('ais_ship_type', sa.String(length=40), nullable=True),
        sa.Column('verification', sa.String(length=12), nullable=False),
        sa.Column('verification_note', sa.Text(), nullable=True),
        sa.Column('last_latitude', sa.Float(), nullable=True),
        sa.Column('last_longitude', sa.Float(), nullable=True),
        sa.Column('last_sog', sa.Float(), nullable=True),
        sa.Column('last_cog', sa.Float(), nullable=True),
        sa.Column('last_nav_status', sa.String(length=40), nullable=True),
        sa.Column('last_position_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('status_detail', sa.Text(), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('risk_level', sa.String(length=10), nullable=True),
        sa.Column('risk_detail', sa.Text(), nullable=True),
        sa.Column('wave_height_m', sa.Float(), nullable=True),
        sa.Column('wind_gusts_kmh', sa.Float(), nullable=True),
        sa.Column('corridor', sa.String(length=80), nullable=True),
        sa.Column('lane_id', sa.String(length=80), nullable=True),
        sa.Column('lane_risk', sa.Integer(), nullable=True),
        sa.Column('lane_offset_nm', sa.Float(), nullable=True),
        sa.Column('nearest_port', sa.String(length=80), nullable=True),
        sa.Column('nearest_port_nm', sa.Float(), nullable=True),
        sa.Column('monitored_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('fleet_vessels', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_fleet_vessels_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fleet_vessels_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fleet_vessels_imo'), ['imo'], unique=False)
        batch_op.create_index(batch_op.f('ix_fleet_vessels_mmsi'), ['mmsi'], unique=True)

    op.create_table(
        'fleet_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vessel_id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('severity', sa.String(length=10), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['vessel_id'], ['fleet_vessels.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('fleet_alerts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_fleet_alerts_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fleet_alerts_vessel_id'), ['vessel_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fleet_alerts_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fleet_alerts_created_at'), ['created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('fleet_alerts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fleet_alerts_created_at'))
        batch_op.drop_index(batch_op.f('ix_fleet_alerts_owner_id'))
        batch_op.drop_index(batch_op.f('ix_fleet_alerts_vessel_id'))
        batch_op.drop_index(batch_op.f('ix_fleet_alerts_id'))
    op.drop_table('fleet_alerts')

    with op.batch_alter_table('fleet_vessels', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fleet_vessels_mmsi'))
        batch_op.drop_index(batch_op.f('ix_fleet_vessels_imo'))
        batch_op.drop_index(batch_op.f('ix_fleet_vessels_owner_id'))
        batch_op.drop_index(batch_op.f('ix_fleet_vessels_id'))
    op.drop_table('fleet_vessels')
