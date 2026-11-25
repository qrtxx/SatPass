"""observer owners: each location belongs to a user

Revision ID: 171d31633d29
Revises: bca89904aa00
Create Date: 2026-11-25 15:13:53.390744

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '171d31633d29'
down_revision: Union[str, Sequence[str], None] = 'bca89904aa00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Give every observer an owner. Existing ones (e.g. the seeded Almaty) go to the admin."""
    # owner_id can't be NOT NULL right away: rows already exist. Add it, fill it in, then require it.
    op.add_column('observers', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.execute("UPDATE observers SET owner_id = (SELECT id FROM users WHERE username = 'admin')")
    op.alter_column('observers', 'owner_id', nullable=False)
    op.create_index(op.f('ix_observers_owner_id'), 'observers', ['owner_id'], unique=False)
    op.create_foreign_key(op.f('fk_observers_owner_id_users'), 'observers', 'users', ['owner_id'], ['id'], ondelete='CASCADE')
    # Location names become unique per owner instead of globally.
    op.drop_index(op.f('uq_observers_name_lower'), table_name='observers')
    op.create_index('uq_observers_owner_name', 'observers', ['owner_id', sa.literal_column('lower(name)')], unique=True)


def downgrade() -> None:
    """Undo ownership: only the admin's locations survive.

    Going back removes accounts (0004 drops users), so other users' locations are deleted with them.
    Otherwise two users' locations with the same name would break the old global unique index."""
    op.execute("DELETE FROM observers WHERE owner_id <> (SELECT id FROM users WHERE username = 'admin')")
    op.drop_constraint(op.f('fk_observers_owner_id_users'), 'observers', type_='foreignkey')
    op.drop_index('uq_observers_owner_name', table_name='observers')
    op.drop_index(op.f('ix_observers_owner_id'), table_name='observers')
    op.create_index(op.f('uq_observers_name_lower'), 'observers', [sa.literal_column('lower(name::text)')], unique=True)
    op.drop_column('observers', 'owner_id')
    # ### end Alembic commands ###
