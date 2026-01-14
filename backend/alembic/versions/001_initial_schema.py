"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema."""

    # Ensure extensions exist
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('agent_name', sa.String(100), nullable=True, index=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), index=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )

    # Agent decisions tracking table
    op.create_table(
        'agent_decisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('agent_name', sa.String(100), nullable=False, index=True),
        sa.Column('decision_type', sa.String(100), nullable=False, index=True),
        sa.Column('input_data', postgresql.JSONB, nullable=True),
        sa.Column('output_data', postgresql.JSONB, nullable=True),
        sa.Column('tools_used', postgresql.JSONB, nullable=True),
        sa.Column('reasoning', sa.Text, nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), index=True),
        sa.Column('execution_time_ms', sa.Integer, nullable=True),
    )

    # Agent learnings table with vector embeddings
    # Note: Create table first, then add vector column (pgvector requires raw SQL)
    op.create_table(
        'agent_learnings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('content', sa.Text, nullable=False),
        # embedding column added separately below using raw SQL
        sa.Column('source_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('agent_name', sa.String(100), nullable=False, index=True),
        sa.Column('learning_type', sa.String(100), nullable=False, index=True),
        sa.Column('confidence_score', sa.Float, nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), index=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )

    # Add vector embedding column using raw SQL (pgvector type)
    op.execute('ALTER TABLE agent_learnings ADD COLUMN embedding vector(1536)')

    # Create vector index for similarity search
    op.execute('''
        CREATE INDEX agent_learnings_embedding_idx
        ON agent_learnings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')

    # Query cache table
    op.create_table(
        'query_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('query_hash', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('query_text', sa.Text, nullable=False),
        sa.Column('result', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False, index=True),
    )

    # Create indexes for performance
    op.create_index('idx_sessions_user_created', 'sessions', ['user_id', 'created_at'])
    op.create_index('idx_messages_session_timestamp', 'messages', ['session_id', 'timestamp'])
    op.create_index('idx_decisions_agent_timestamp', 'agent_decisions', ['agent_name', 'timestamp'])
    op.create_index('idx_learnings_agent_created', 'agent_learnings', ['agent_name', 'created_at'])
    op.create_index('idx_learnings_type_confidence', 'agent_learnings', ['learning_type', 'confidence_score'])

    # Create trigger for updating updated_at timestamp
    op.execute('''
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    ''')

    op.execute('''
        CREATE TRIGGER update_sessions_updated_at
        BEFORE UPDATE ON sessions
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    ''')


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('query_cache')
    op.drop_table('agent_learnings')
    op.drop_table('agent_decisions')
    op.drop_table('messages')
    op.drop_table('sessions')

    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions')
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')
