"""
Snowflake tool for querying DV360 data.
"""
from typing import Dict, Any, List, Optional
import hashlib
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

import snowflake.connector
from snowflake.connector import DictCursor
from langchain_core.tools import tool

from ..core.config import settings
from ..core.cache import get_query_cache, set_query_cache
from ..core.telemetry import get_logger


logger = get_logger(__name__)

# Thread pool for sync Snowflake connector
executor = ThreadPoolExecutor(max_workers=5)


class SnowflakeTool:
    """
    Tool for querying Snowflake DV360 data.

    Features:
    - Connection pooling
    - Query caching
    - Common DV360 query templates
    - Async execution wrapper
    """

    def __init__(self):
        """Initialize Snowflake connection with key pair or password authentication."""
        self.connection_params = {
            "account": settings.snowflake_account,
            "user": settings.snowflake_user,
            "warehouse": settings.snowflake_warehouse,
            "database": settings.snowflake_database,
            "schema": settings.snowflake_schema,
        }

        if settings.snowflake_role:
            self.connection_params["role"] = settings.snowflake_role

        # Check for key pair authentication (preferred - no 2FA!)
        if hasattr(settings, 'snowflake_private_key_path') and settings.snowflake_private_key_path:
            try:
                # Read private key file using the exact pattern from user
                with open(settings.snowflake_private_key_path, "rb") as key_file:
                    private_key = key_file.read()

                self.connection_params["private_key"] = private_key
                logger.info(
                    "Snowflake initialized with key pair authentication (no 2FA)",
                    database=settings.snowflake_database,
                    key_path=settings.snowflake_private_key_path
                )
            except Exception as e:
                logger.error(
                    "Failed to load private key, falling back to password auth",
                    error_message=str(e),
                    key_path=settings.snowflake_private_key_path
                )
                # Fall back to password if key loading fails
                if settings.snowflake_password:
                    self.connection_params["password"] = settings.snowflake_password
        else:
            # Use password authentication (may require 2FA)
            if settings.snowflake_password:
                self.connection_params["password"] = settings.snowflake_password
                logger.info(
                    "Snowflake initialized with password authentication",
                    database=settings.snowflake_database
                )
            else:
                logger.warning("No Snowflake authentication method configured")

        logger.info("Snowflake tool initialized", database=settings.snowflake_database)

    def _get_connection(self):
        """Get a Snowflake connection."""
        return snowflake.connector.connect(**self.connection_params)

    def _execute_query_sync(self, query: str) -> List[Dict[str, Any]]:
        """Execute query synchronously."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(DictCursor)
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()


            return results
        finally:
            if conn:
                conn.close()

    async def execute_query(
        self,
        query: str,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Execute a Snowflake query asynchronously.

        Args:
            query: SQL query to execute
            use_cache: Whether to use query cache

        Returns:
            List of result dictionaries
        """
        start_time = time.time()

        # Check cache
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        if use_cache:
            cached = await get_query_cache(query_hash)
            if cached:
                logger.info("Query cache hit", query_hash=query_hash)
                return cached

        # Execute query in thread pool (Snowflake connector is sync)
        try:
            logger.info("Executing Snowflake query", query_preview=query[:100])

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                executor,
                self._execute_query_sync,
                query
            )

            duration = time.time() - start_time
            logger.info(
                "Query executed successfully",
                duration_seconds=round(duration, 2),
                result_count=len(results)
            )

            # Cache results
            if use_cache:
                await set_query_cache(query_hash, results)

            return results

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Query execution failed",
                error=str(e),
                duration_seconds=round(duration, 2)
            )
            raise

    async def get_campaign_performance(
        self,
        insertion_order: Optional[str] = None,
        advertiser: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get campaign performance metrics.

        Args:
            insertion_order: Optional campaign ID filter
            advertiser: Optional advertiser ID filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            limit: Maximum number of results

        Returns:
            List of campaign performance records
        """
        # Build query with filters
        query_parts = ["""
            select 
            advertiser , 
            date ,
            insertion_order ,
            sum(spend_gbp) SPEND , 
            sum(impressions) impressions , 
            sum(clicks) clicks ,             
            sum(total_conversions_pm) TOTAL_CONVERSIONS , 
            sum(total_revenue_gbp_pm) TOTAL_REVENUE 
            from reports.reporting_revamp.ALL_PERFORMANCE_AGG
            where advertiser = 'Quiz'
        """]

        if insertion_order:
            query_parts.append(f"AND insertion_order = '{insertion_order}'")
        if advertiser:
            query_parts.append(f"AND advertiser_id = '{advertiser}'")
        if start_date:
            query_parts.append(f"AND date >= '{start_date}'")
        if end_date:
            query_parts.append(f"AND date <= '{end_date}'")

        query_parts.append(f"ORDER BY date DESC LIMIT {limit}")

        query = "\n".join(query_parts)
        return await self.execute_query(query)

    async def get_budget_pacing(
        self,
        campaign_id: str,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get budget pacing analysis for a campaign.

        Args:
            campaign_id: Campaign ID
            period_days: Number of days to analyze

        Returns:
            Budget pacing metrics
        """
        query = f"""
            select *
            from reports.multi_agent.DV360_BUDGETS_QUIZ
        """

        results = await self.execute_query(query)
        return results[0] if results else {}

    async def get_audience_performance(
        self,
        advertiser_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_impressions: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get audience segment performance.

        Args:
            advertiser_id: Advertiser ID
            start_date: Optional start date
            end_date: Optional end date
            min_impressions: Minimum impressions filter

        Returns:
            List of audience performance records
        """
        query_parts = [f"""
            select 
            advertiser , 
            date ,
            insertion_order ,
            line_item ,
            sum(spend_gbp) SPEND , 
            sum(impressions) impressions , 
            sum(clicks) clicks ,             
            sum(total_conversions_pm) TOTAL_CONVERSIONS , 
            sum(total_revenue_gbp_pm) TOTAL_REVENUE 
            from reports.reporting_revamp.ALL_PERFORMANCE_AGG
            where advertiser = 'Quiz'
        """]

        if start_date:
            query_parts.append(f"AND date >= '{start_date}'")
        if end_date:
            query_parts.append(f"AND date <= '{end_date}'")

        if start_date:
            query_parts.append(f"AND date >= '{start_date}'")
        if end_date:
            query_parts.append(f"AND date <= '{end_date}'")

        query_parts.append("""
            group by 1,2,3,4
        """)

        query = "\n".join(query_parts)
        return await self.execute_query(query)

    async def get_creative_performance(
        self,
        campaign_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get creative performance metrics.

        Args:
            campaign_id: Campaign ID
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            List of creative performance records
        """
        query_parts = [f"""
            select 
            advertiser , 
            date ,
            insertion_order ,
            REGEXP_REPLACE(CREATIVE, '_[^_]*$', '') AS creative_name ,
            creative_size ,
            sum(spend_gbp) SPEND , 
            sum(impressions) impressions , 
            sum(clicks) clicks ,             
            sum(total_conversions_pm) TOTAL_CONVERSIONS , 
            sum(total_revenue_gbp_pm) TOTAL_REVENUE 
            from reports.reporting_revamp.creative_name_agg
            where advertiser = 'Quiz'
            """]

        if start_date:
            query_parts.append(f"AND date >= '{start_date}'")
        if end_date:
            query_parts.append(f"AND date <= '{end_date}'")

        query_parts.append("""
            group by 1,2,3,4,5
        """)

        query = "\n".join(query_parts)
        return await self.execute_query(query)

    def to_langchain_tool(self):
        """Convert to LangChain tool for agent use."""
        @tool
        async def query_dv360_data(query: str) -> str:
            """
            Query DV360 data from Snowflake.

            Args:
                query: SQL query to execute

            Returns:
                JSON string of results
            """
            import json
            results = await self.execute_query(query)
            return json.dumps(results, default=str)

        return query_dv360_data


# Global instance
snowflake_tool = SnowflakeTool()
