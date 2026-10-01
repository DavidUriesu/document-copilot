"""Synchronize Supabase Auth users with application users.

Revision ID: 20261001_0002
Revises: 20260930_0001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261001_0002"
down_revision: str | Sequence[str] | None = "20260930_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create and backfill application users from Supabase Auth."""
    op.execute(
        """
        CREATE FUNCTION public.sync_auth_user()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        AS $$
        BEGIN
            IF NEW.email IS NULL THEN
                RETURN NEW;
            END IF;

            INSERT INTO public.users (id, email)
            VALUES (NEW.id, NEW.email)
            ON CONFLICT (id) DO UPDATE
            SET email = EXCLUDED.email, updated_at = now();

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER sync_auth_user_after_write
        AFTER INSERT OR UPDATE OF email ON auth.users
        FOR EACH ROW EXECUTE FUNCTION public.sync_auth_user()
        """
    )
    op.execute(
        """
        INSERT INTO public.users (id, email)
        SELECT id, email
        FROM auth.users
        WHERE email IS NOT NULL
        ON CONFLICT (id) DO UPDATE
        SET email = EXCLUDED.email, updated_at = now()
        """
    )


def downgrade() -> None:
    """Stop synchronizing Supabase Auth users."""
    op.execute("DROP TRIGGER sync_auth_user_after_write ON auth.users")
    op.execute("DROP FUNCTION public.sync_auth_user()")
