#!/usr/bin/env python3
"""
Test script to verify the DV360 Multi-Agent System setup.
Tests configuration, database, Redis, and core components.

Usage:
    # Inside Docker container (recommended)
    docker exec -it dv360-backend python test_setup.py
    
    # Or locally (requires dependencies)
    python test_setup.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

try:
    from src.core.config import settings
    from src.core.database import init_db, check_db_health, ensure_pgvector_extension, close_db
    from src.core.cache import init_redis, check_redis_health, close_redis
    from src.core.telemetry import get_logger
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Warning: Some dependencies are missing: {e}")
    print("   Install dependencies: cd backend && pip install -r requirements.txt")
    print("   Or run inside Docker: docker exec -it dv360-backend python test_setup.py")
    DEPENDENCIES_AVAILABLE = False
    sys.exit(1)

logger = get_logger(__name__) if DEPENDENCIES_AVAILABLE else None


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗{Colors.RESET} {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {text}")


async def test_configuration():
    """Test configuration loading."""
    print_header("Testing Configuration")
    
    checks = []
    
    # Environment
    print_info(f"Environment: {settings.environment}")
    checks.append(("Environment set", True))
    
    # API Configuration
    print_info(f"API Host: {settings.api_host}:{settings.api_port}")
    checks.append(("API configuration", True))
    
    # Database Configuration
    print_info(f"Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    print_info(f"Database User: {settings.postgres_user}")
    checks.append(("Database configuration", True))
    
    # Redis Configuration
    print_info(f"Redis: {settings.redis_host}:{settings.redis_port}")
    checks.append(("Redis configuration", True))
    
    # LLM Configuration
    has_openai = bool(settings.openai_api_key)
    has_anthropic = bool(settings.anthropic_api_key)
    
    if has_openai:
        print_success(f"OpenAI API key configured (model: {settings.openai_model})")
    else:
        print_warning("OpenAI API key not configured")
    
    if has_anthropic:
        print_success(f"Anthropic API key configured (model: {settings.anthropic_model})")
    else:
        print_warning("Anthropic API key not configured")
    
    if not has_openai and not has_anthropic:
        print_error("No LLM API keys configured - agents will not work!")
        checks.append(("LLM configuration", False))
    else:
        checks.append(("LLM configuration", True))
    
    # Snowflake Configuration
    has_snowflake = bool(
        settings.snowflake_account and
        settings.snowflake_user and
        settings.snowflake_password
    )
    
    if has_snowflake:
        print_success(f"Snowflake configured: {settings.snowflake_account}")
        print_info(f"  Database: {settings.snowflake_database}")
        print_info(f"  Schema: {settings.snowflake_schema}")
        print_info(f"  Warehouse: {settings.snowflake_warehouse}")
    else:
        print_warning("Snowflake not configured - data queries will fail")
    
    checks.append(("Snowflake configuration", has_snowflake))
    
    # Memory Configuration
    print_info(f"Vector dimension: {settings.vector_dimension}")
    print_info(f"Memory top K: {settings.memory_top_k}")
    checks.append(("Memory configuration", True))
    
    return all(check[1] for check in checks)


async def test_database():
    """Test database connectivity."""
    print_header("Testing Database Connection")
    
    try:
        print_info("Initializing database connection...")
        await init_db()
        print_success("Database connection initialized")
        
        print_info("Checking database health...")
        is_healthy = await check_db_health()
        
        if is_healthy:
            print_success("Database is healthy")
        else:
            print_error("Database health check failed")
            return False
        
        print_info("Ensuring pgvector extension...")
        await ensure_pgvector_extension()
        print_success("pgvector extension verified")
        
        return True
        
    except Exception as e:
        print_error(f"Database test failed: {str(e)}")
        print_info("Make sure PostgreSQL is running and accessible")
        return False


async def test_redis():
    """Test Redis connectivity."""
    print_header("Testing Redis Connection")
    
    try:
        print_info("Initializing Redis connection...")
        await init_redis()
        print_success("Redis connection initialized")
        
        print_info("Checking Redis health...")
        is_healthy = await check_redis_health()
        
        if is_healthy:
            print_success("Redis is healthy")
        else:
            print_error("Redis health check failed")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Redis test failed: {str(e)}")
        print_info("Make sure Redis is running and accessible")
        print_info(f"  Host: {settings.redis_host}:{settings.redis_port}")
        if settings.redis_password:
            print_info("  Password: configured")
        return False


async def test_core_components():
    """Test core components."""
    print_header("Testing Core Components")
    
    checks = []
    
    # Check if modules can be imported
    try:
        from src.memory.vector_store import VectorStore
        print_success("VectorStore module imported")
        checks.append(True)
    except Exception as e:
        print_error(f"VectorStore import failed: {e}")
        checks.append(False)
    
    try:
        from src.memory.session_manager import SessionManager
        print_success("SessionManager module imported")
        checks.append(True)
    except Exception as e:
        print_error(f"SessionManager import failed: {e}")
        checks.append(False)
    
    try:
        from src.tools.snowflake_tool import SnowflakeTool
        print_success("SnowflakeTool module imported")
        checks.append(True)
    except Exception as e:
        print_error(f"SnowflakeTool import failed: {e}")
        checks.append(False)
    
    try:
        from src.tools.decision_logger import DecisionLogger
        print_success("DecisionLogger module imported")
        checks.append(True)
    except Exception as e:
        print_error(f"DecisionLogger import failed: {e}")
        checks.append(False)
    
    try:
        from src.agents.base import BaseAgent
        print_success("BaseAgent module imported")
        checks.append(True)
    except Exception as e:
        print_error(f"BaseAgent import failed: {e}")
        checks.append(False)
    
    return all(checks)


async def test_api_endpoints():
    """Test API endpoints (if server is running)."""
    print_header("Testing API Endpoints")
    
    import httpx
    
    base_url = f"http://{settings.api_host}:{settings.api_port}"
    
    endpoints = [
        ("/", "Root endpoint"),
        ("/health", "Health check"),
        ("/health/liveness", "Liveness probe"),
        ("/health/readiness", "Readiness probe"),
    ]
    
    results = []
    
    for endpoint, description in endpoints:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{base_url}{endpoint}")
                
                if response.status_code == 200:
                    print_success(f"{description}: {endpoint} (200 OK)")
                    results.append(True)
                else:
                    print_warning(f"{description}: {endpoint} ({response.status_code})")
                    results.append(False)
        except httpx.ConnectError:
            print_warning(f"{description}: Server not running at {base_url}")
            results.append(False)
        except Exception as e:
            print_error(f"{description}: {str(e)}")
            results.append(False)
    
    return any(results)  # At least one endpoint should work if server is running


async def main():
    """Run all tests."""
    print_header("DV360 Multi-Agent System - Setup Test")
    
    results = {}
    
    # Test configuration
    results["configuration"] = await test_configuration()
    
    # Test database
    try:
        results["database"] = await test_database()
    except Exception as e:
        print_error(f"Database test error: {e}")
        results["database"] = False
    
    # Test Redis
    try:
        results["redis"] = await test_redis()
    except Exception as e:
        print_error(f"Redis test error: {e}")
        results["redis"] = False
    
    # Test core components
    results["components"] = await test_core_components()
    
    # Test API endpoints (optional - server may not be running)
    results["api"] = await test_api_endpoints()
    
    # Cleanup
    try:
        await close_db()
    except:
        pass
    
    try:
        await close_redis()
    except:
        pass
    
    # Summary
    print_header("Test Summary")
    
    for test_name, passed in results.items():
        if passed:
            print_success(f"{test_name.capitalize()}: PASSED")
        else:
            print_error(f"{test_name.capitalize()}: FAILED")
    
    all_passed = all(results.values())
    
    if all_passed:
        print_success("\n🎉 All tests passed! System is ready.")
    else:
        print_warning("\n⚠️  Some tests failed. Review the output above.")
        print_info("Note: API endpoint test may fail if server is not running")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

