#!/usr/bin/env python3
"""Redis performance testing script for KEN-E workloads."""

import asyncio
import json
import os
import random
import statistics
import string
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kene_api.redis_client import get_redis_service

class RedisPerformanceTester:
    """Performance tester for Redis operations."""
    
    def __init__(self):
        self.redis_service = get_redis_service()
        self.results: Dict[str, List[float]] = {}
    
    def generate_test_data(self, size: str = "medium") -> Dict[str, Any]:
        """Generate test data of different sizes."""
        if size == "small":
            return {
                "id": "".join(random.choices(string.ascii_letters, k=10)),
                "value": random.randint(1, 1000),
                "timestamp": time.time()
            }
        elif size == "medium":
            return {
                "user_id": "".join(random.choices(string.ascii_letters + string.digits, k=12)),
                "organization_id": "".join(random.choices(string.ascii_letters + string.digits, k=12)),
                "permissions": ["read", "write", "admin"][:random.randint(1, 3)],
                "profile": {
                    "name": "Test User",
                    "email": f"test{random.randint(1, 10000)}@example.com",
                    "preferences": {
                        "theme": random.choice(["light", "dark"]),
                        "notifications": random.choice([True, False])
                    }
                },
                "metadata": {
                    "created_at": time.time(),
                    "last_login": time.time() - random.randint(0, 86400),
                    "login_count": random.randint(1, 1000)
                }
            }
        else:  # large
            return {
                "account_id": "".join(random.choices(string.ascii_letters + string.digits, k=12)),
                "metrics": [
                    {
                        "metric_name": f"metric_{i}",
                        "value": random.random() * 100,
                        "timestamp": time.time() - (i * 3600),
                        "dimensions": {
                            "source": random.choice(["api", "frontend", "batch"]),
                            "region": random.choice(["us-east-1", "us-west-2", "eu-west-1"])
                        }
                    }
                    for i in range(100)
                ],
                "industry_keywords": [
                    {
                        "keyword": f"keyword_{i}",
                        "relevance": random.random(),
                        "source": random.choice(["manual", "auto", "import"])
                    }
                    for i in range(50)
                ],
                "monitoring_topics": [
                    f"topic_{i}" for i in range(20)
                ]
            }
    
    def measure_operation(self, operation_name: str, operation_func, *args, **kwargs):
        """Measure the time of a single operation."""
        start_time = time.time()
        result = operation_func(*args, **kwargs)
        duration = time.time() - start_time
        
        if operation_name not in self.results:
            self.results[operation_name] = []
        self.results[operation_name].append(duration)
        
        return result, duration
    
    def test_basic_operations(self, num_operations: int = 1000):
        """Test basic SET/GET operations."""
        print(f"🧪 Testing {num_operations} basic operations...")
        
        # Test SET operations
        for i in range(num_operations):
            key = f"ken-e:test:basic:{i}"
            value = f"test_value_{i}"
            
            self.measure_operation("basic_set", self.redis_service.set, key, value, 300)
            
            if i % 100 == 0:
                print(f"  Completed {i}/{num_operations} SET operations")
        
        # Test GET operations
        for i in range(num_operations):
            key = f"ken-e:test:basic:{i}"
            
            self.measure_operation("basic_get", self.redis_service.get, key)
            
            if i % 100 == 0:
                print(f"  Completed {i}/{num_operations} GET operations")
    
    def test_json_operations(self, num_operations: int = 500):
        """Test JSON SET/GET operations with different data sizes."""
        print(f"🧪 Testing {num_operations} JSON operations...")
        
        sizes = ["small", "medium", "large"]
        
        for size in sizes:
            print(f"  Testing {size} JSON data...")
            
            # SET operations
            for i in range(num_operations // len(sizes)):
                key = f"ken-e:test:json:{size}:{i}"
                data = self.generate_test_data(size)
                
                self.measure_operation(f"json_set_{size}", self.redis_service.set_json, key, data, 600)
            
            # GET operations
            for i in range(num_operations // len(sizes)):
                key = f"ken-e:test:json:{size}:{i}"
                
                self.measure_operation(f"json_get_{size}", self.redis_service.get_json, key)
    
    def test_concurrent_operations(self, num_threads: int = 10, operations_per_thread: int = 100):
        """Test concurrent operations."""
        print(f"🧪 Testing concurrent operations ({num_threads} threads, {operations_per_thread} ops/thread)...")
        
        def worker_thread(thread_id: int):
            """Worker function for concurrent testing."""
            thread_results = []
            
            for i in range(operations_per_thread):
                key = f"ken-e:test:concurrent:{thread_id}:{i}"
                data = self.generate_test_data("medium")
                
                # SET operation
                start_time = time.time()
                self.redis_service.set_json(key, data, 300)
                set_duration = time.time() - start_time
                thread_results.append(("concurrent_set", set_duration))
                
                # GET operation
                start_time = time.time()
                self.redis_service.get_json(key)
                get_duration = time.time() - start_time
                thread_results.append(("concurrent_get", get_duration))
            
            return thread_results
        
        # Execute concurrent operations
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(num_threads)]
            
            all_results = []
            for future in futures:
                thread_results = future.result()
                all_results.extend(thread_results)
        
        # Add results to main results
        for operation_name, duration in all_results:
            if operation_name not in self.results:
                self.results[operation_name] = []
            self.results[operation_name].append(duration)
    
    def test_cache_patterns(self):
        """Test common KEN-E cache patterns."""
        print("🧪 Testing KEN-E cache patterns...")
        
        # Industry keywords pattern
        industry_data = [
            {"keyword": "artificial intelligence", "relevance": 0.95},
            {"keyword": "machine learning", "relevance": 0.90},
            {"keyword": "cloud computing", "relevance": 0.85}
        ]
        
        for industry in ["technology", "healthcare", "finance", "retail", "manufacturing"]:
            key = f"industry_keywords:{industry}"
            self.measure_operation("industry_cache_set", self.redis_service.set_json, key, industry_data, 1800)
            self.measure_operation("industry_cache_get", self.redis_service.get_json, key)
        
        # User context pattern
        for user_id in range(100):
            user_context = {
                "user_id": f"user_{user_id}",
                "organization_id": f"org_{user_id // 10}",
                "permissions": ["read", "write"],
                "cached_at": time.time()
            }
            key = f"user_context:user_{user_id}"
            self.measure_operation("user_context_set", self.redis_service.set_json, key, user_context, 300)
            self.measure_operation("user_context_get", self.redis_service.get_json, key)
        
        # Monitoring topics pattern
        for account_id in range(50):
            monitoring_data = {
                "topics": [f"topic_{i}" for i in range(10)],
                "last_updated": time.time(),
                "account_id": f"account_{account_id}"
            }
            key = f"monitoring_topics:account_{account_id}"
            self.measure_operation("monitoring_cache_set", self.redis_service.set_json, key, monitoring_data, 900)
            self.measure_operation("monitoring_cache_get", self.redis_service.get_json, key)
    
    def cleanup_test_data(self):
        """Clean up all test data."""
        print("🧹 Cleaning up test data...")
        
        patterns = [
            "ken-e:test:basic:*",
            "ken-e:test:json:*",
            "ken-e:test:concurrent:*",
            "industry_keywords:*",
            "user_context:*",
            "monitoring_topics:*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            try:
                if hasattr(self.redis_service, 'client'):
                    keys = list(self.redis_service.client.scan_iter(match=pattern))
                    if keys:
                        deleted = self.redis_service.client.delete(*keys)
                        total_deleted += deleted
                        print(f"  Deleted {deleted} keys matching {pattern}")
            except Exception as e:
                print(f"  Warning: Could not delete pattern {pattern}: {e}")
        
        print(f"  Total deleted: {total_deleted} keys")
    
    def print_results(self):
        """Print performance test results."""
        print("\n📊 Performance Test Results")
        print("=" * 80)
        
        overall_stats = []
        
        for operation, times in self.results.items():
            if not times:
                continue
                
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            median_time = statistics.median(times)
            p95_time = times[int(len(times) * 0.95)] if len(times) > 20 else max_time
            
            overall_stats.append(avg_time)
            
            print(f"\n{operation.upper().replace('_', ' ')}:")
            print(f"  Operations: {len(times):,}")
            print(f"  Average:    {avg_time*1000:.2f}ms")
            print(f"  Median:     {median_time*1000:.2f}ms")
            print(f"  Min:        {min_time*1000:.2f}ms")
            print(f"  Max:        {max_time*1000:.2f}ms")
            print(f"  95th %ile:  {p95_time*1000:.2f}ms")
            
            # Performance assessment
            if avg_time < 0.001:  # 1ms
                status = "🚀 EXCELLENT"
            elif avg_time < 0.005:  # 5ms
                status = "✅ GOOD"
            elif avg_time < 0.020:  # 20ms
                status = "⚠️  ACCEPTABLE"
            else:
                status = "🐌 SLOW"
            
            print(f"  Status:     {status}")
        
        # Overall summary
        if overall_stats:
            overall_avg = statistics.mean(overall_stats)
            print(f"\n🎯 OVERALL PERFORMANCE")
            print(f"   Average across all operations: {overall_avg*1000:.2f}ms")
            
            if overall_avg < 0.005:
                print("   🚀 Excellent performance - ready for production!")
            elif overall_avg < 0.020:
                print("   ✅ Good performance - suitable for production")
            elif overall_avg < 0.050:
                print("   ⚠️  Acceptable performance - monitor closely")
            else:
                print("   🐌 Poor performance - optimization needed")

def main():
    """Run Redis performance tests."""
    print("🚀 KEN-E Redis Performance Test")
    print("=" * 50)
    
    tester = RedisPerformanceTester()
    
    # Check Redis availability
    if not tester.redis_service.is_available():
        print("❌ Redis is not available. Please check your configuration.")
        return 1
    
    print("✅ Redis connection established")
    print(f"📡 Host: {os.getenv('REDIS_HOST', 'localhost')}")
    print(f"🔌 Port: {os.getenv('REDIS_PORT', '6379')}")
    
    try:
        # Run performance tests
        start_time = time.time()
        
        # Basic operations test
        tester.test_basic_operations(1000)
        
        # JSON operations test  
        tester.test_json_operations(500)
        
        # Concurrent operations test
        tester.test_concurrent_operations(10, 50)
        
        # Cache patterns test
        tester.test_cache_patterns()
        
        total_time = time.time() - start_time
        
        # Print results
        tester.print_results()
        
        print(f"\n⏱️  Total test time: {total_time:.2f} seconds")
        
        # Cleanup
        tester.cleanup_test_data()
        
        print("\n✅ Performance tests completed successfully!")
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        tester.cleanup_test_data()
        return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        tester.cleanup_test_data()
        return 1

if __name__ == "__main__":
    sys.exit(main())