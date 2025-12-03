"""
Retry Handler with Exponential Backoff
======================================
Provides intelligent retry logic for API calls with rate limit handling.
"""

import asyncio
import time
from typing import Callable, Any, Optional, TypeVar
from functools import wraps
import random

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


def calculate_backoff_delay(
    attempt: int,
    config: RetryConfig
) -> float:
    """
    Calculate delay for exponential backoff with optional jitter.
    
    Args:
        attempt: Current retry attempt number (0-indexed)
        config: Retry configuration
        
    Returns:
        Delay in seconds
    """
    delay = min(
        config.initial_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
    
    if config.jitter:
        delay = delay * (0.5 + random.random())
    
    return delay


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error should trigger retry
    """
    error_str = str(error).lower()
    
    retryable_patterns = [
        '429',
        'resource_exhausted',
        'rate limit',
        'quota',
        'too many requests',
        '503',
        'service unavailable',
        'overloaded',
        'timeout',
        'connection',
        'network'
    ]
    
    return any(pattern in error_str for pattern in retryable_patterns)


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    log_func: Optional[Callable[[str], None]] = None
):
    """
    Decorator for synchronous functions with exponential backoff retry.
    
    Args:
        config: Retry configuration (uses defaults if None)
        log_func: Optional logging function
        
    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    if not is_retryable_error(e):
                        if log_func:
                            log_func(f"Non-retryable error: {e}")
                        raise
                    
                    if attempt < config.max_retries:
                        delay = calculate_backoff_delay(attempt, config)
                        
                        if log_func:
                            log_func(
                                f"Retry {attempt + 1}/{config.max_retries} "
                                f"after {delay:.2f}s due to: {e}"
                            )
                        
                        time.sleep(delay)
                    else:
                        if log_func:
                            log_func(
                                f"Max retries ({config.max_retries}) exceeded"
                            )
            
            raise last_exception
        
        return wrapper
    return decorator


def async_retry_with_backoff(
    config: Optional[RetryConfig] = None,
    log_func: Optional[Callable[[str], None]] = None
):
    """
    Decorator for async functions with exponential backoff retry.
    
    Args:
        config: Retry configuration (uses defaults if None)
        log_func: Optional logging function
        
    Returns:
        Decorated async function with retry logic
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    if not is_retryable_error(e):
                        if log_func:
                            log_func(f"Non-retryable error: {e}")
                        raise
                    
                    if attempt < config.max_retries:
                        delay = calculate_backoff_delay(attempt, config)
                        
                        if log_func:
                            log_func(
                                f"Retry {attempt + 1}/{config.max_retries} "
                                f"after {delay:.2f}s due to: {e}"
                            )
                        
                        await asyncio.sleep(delay)
                    else:
                        if log_func:
                            log_func(
                                f"Max retries ({config.max_retries}) exceeded"
                            )
            
            raise last_exception
        
        return wrapper
    return decorator


class RetryHandler:
    """
    Retry handler for managing API calls with rate limits.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.last_request_time = 0
        self.min_request_interval = 0.2
    
    async def execute_with_retry(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute async function with retry logic and rate limiting.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                self.last_request_time = time.time()
                result = await func(*args, **kwargs)
                return result
                
            except Exception as e:
                last_exception = e
                
                if not is_retryable_error(e):
                    raise
                
                if attempt < self.config.max_retries:
                    delay = calculate_backoff_delay(attempt, self.config)
                    print(
                        f"[RETRY] Attempt {attempt + 1}/{self.config.max_retries} "
                        f"failed, retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
        
        raise last_exception


default_retry_handler = RetryHandler(
    RetryConfig(
        max_retries=3,
        initial_delay=2.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True
    )
)


def get_retry_handler() -> RetryHandler:
    """Get the default retry handler instance."""
    return default_retry_handler
