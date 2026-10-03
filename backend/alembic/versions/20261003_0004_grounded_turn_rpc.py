"""Add atomic grounded chat-turn persistence.

Revision ID: 20261003_0004
Revises: 20261003_0003
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261003_0004"
down_revision: str | Sequence[str] | None = "20261003_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create a caller-scoped transaction for messages and citations."""
    op.execute(
        """
        CREATE FUNCTION public.append_grounded_turn(
            p_thread_id uuid,
            p_user_message_id uuid,
            p_user_content text,
            p_user_parts jsonb,
            p_assistant_message_id uuid,
            p_assistant_content text,
            p_assistant_parts jsonb,
            p_citations jsonb
        )
        RETURNS TABLE (user_message_id uuid, assistant_message_id uuid)
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = ''
        AS $$
        DECLARE
            next_sequence integer;
            citation jsonb;
        BEGIN
            PERFORM 1
            FROM public.chat_threads
            WHERE id = p_thread_id AND user_id = (SELECT auth.uid())
            FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'chat thread is not owned by caller';
            END IF;

            SELECT coalesce(max(sequence_number) + 1, 0)
            INTO next_sequence
            FROM public.chat_messages
            WHERE thread_id = p_thread_id;

            INSERT INTO public.chat_messages (
                id, thread_id, role, sequence_number, content, parts
            ) VALUES
                (
                    p_user_message_id, p_thread_id, 'user', next_sequence,
                    p_user_content, p_user_parts
                ),
                (
                    p_assistant_message_id, p_thread_id, 'assistant',
                    next_sequence + 1, p_assistant_content, p_assistant_parts
                );

            FOR citation IN SELECT value FROM jsonb_array_elements(p_citations)
            LOOP
                INSERT INTO public.message_citations (
                    message_id, chunk_id, citation_index, excerpt
                ) VALUES (
                    p_assistant_message_id,
                    (citation->>'chunk_id')::uuid,
                    (citation->>'citation_index')::integer,
                    citation->>'excerpt'
                );
            END LOOP;

            UPDATE public.chat_threads
            SET updated_at = now()
            WHERE id = p_thread_id;

            RETURN QUERY SELECT p_user_message_id, p_assistant_message_id;
        END;
        $$
        """
    )
    op.execute(
        """
        REVOKE ALL ON FUNCTION public.append_grounded_turn(
            uuid, uuid, text, jsonb, uuid, text, jsonb, jsonb
        ) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.append_grounded_turn(
            uuid, uuid, text, jsonb, uuid, text, jsonb, jsonb
        ) TO authenticated;
        """
    )


def downgrade() -> None:
    """Drop atomic grounded-turn persistence."""
    op.execute(
        "DROP FUNCTION public.append_grounded_turn("
        "uuid, uuid, text, jsonb, uuid, text, jsonb, jsonb)"
    )
