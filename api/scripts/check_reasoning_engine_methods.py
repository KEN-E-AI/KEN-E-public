#!/usr/bin/env python3
"""
Test script to discover ReasoningEngine methods.
This will help us understand what methods are actually available.
"""

import os
import sys

# Add the API root to the Python path (parent of scripts directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import vertexai
    from vertexai.preview import reasoning_engines
    
    # Try to import agent_engines as well
    try:
        from vertexai import agent_engines
        print("✅ Successfully imported vertexai, reasoning_engines, and agent_engines")
        has_agent_engines = True
    except ImportError as ae_error:
        print(f"✅ Successfully imported vertexai and reasoning_engines")
        print(f"❌ Could not import agent_engines: {ae_error}")
        has_agent_engines = False
    
    # Initialize Vertex AI (using environment variables)
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    agent_engine_id = os.getenv("VERTEX_AI_AGENT_ENGINE_ID")
    
    print(f"Project ID: {project_id}")
    print(f"Location: {location}")
    print(f"Agent Engine ID: {agent_engine_id}")
    
    # Initialize Vertex AI
    vertexai.init(project=project_id, location=location)
    print("✅ Vertex AI initialized")
    
    if not agent_engine_id:
        print("❌ VERTEX_AI_AGENT_ENGINE_ID not set")
        print("Let's inspect both ReasoningEngine and agent_engines (if available):")
        
        # Inspect the ReasoningEngine class
        print(f"\n🔍 ReasoningEngine class type: {reasoning_engines.ReasoningEngine}")
        print(f"🔍 ReasoningEngine class MRO: {reasoning_engines.ReasoningEngine.__mro__}")
        
        # Get class methods and attributes
        print("\n📋 ReasoningEngine class methods and attributes:")
        class_methods = [method for method in dir(reasoning_engines.ReasoningEngine) if not method.startswith('_')]
        for method in sorted(class_methods):
            attr = getattr(reasoning_engines.ReasoningEngine, method, None)
            if callable(attr):
                print(f"  📞 {method}() - class method/function")
            else:
                print(f"  📝 {method} - class attribute")
        
        print(f"\n📊 Total ReasoningEngine class methods: {len([m for m in class_methods if callable(getattr(reasoning_engines.ReasoningEngine, m, None))])}")
        
        # Check agent_engines if available
        if has_agent_engines:
            print(f"\n🔍 agent_engines module contents:")
            agent_engine_attrs = [attr for attr in dir(agent_engines) if not attr.startswith('_')]
            for attr in sorted(agent_engine_attrs):
                obj = getattr(agent_engines, attr, None)
                if callable(obj):
                    print(f"  📞 {attr}() - function")
                elif hasattr(obj, '__class__') and obj.__class__.__name__ != 'str':
                    print(f"  🏷️ {attr} - class/object: {type(obj)}")
                else:
                    print(f"  📝 {attr} - attribute: {obj}")
            
            print(f"\n📊 Total agent_engines attributes: {len(agent_engine_attrs)}")
            
            # Let's specifically look at what agent_engines.get returns
            print(f"\n🧪 Testing agent_engines.get() function signature:")
            try:
                import inspect
                get_signature = inspect.signature(agent_engines.get)
                print(f"  agent_engines.get signature: {get_signature}")
            except Exception as e:
                print(f"  Could not get signature: {e}")
                
            # Test what agent_engines.AgentEngine is
            print(f"\n🧪 Testing agent_engines.AgentEngine:")
            try:
                ae_class = agent_engines.AgentEngine
                print(f"  AgentEngine type: {type(ae_class)}")
                if hasattr(ae_class, '__doc__'):
                    print(f"  AgentEngine doc: {ae_class.__doc__}")
                    
                # Try to see what methods it might have
                if hasattr(ae_class, '__annotations__'):
                    print(f"  AgentEngine annotations: {ae_class.__annotations__}")
            except Exception as e:
                print(f"  Could not inspect AgentEngine: {e}")
        
        # Try to create a dummy instance to see initialization requirements
        print("\n🧪 Trying to understand ReasoningEngine initialization...")
        try:
            # Try with empty string
            dummy_engine = reasoning_engines.ReasoningEngine("")
            print("✅ Can create ReasoningEngine with empty string")
        except Exception as e:
            print(f"❌ Cannot create with empty string: {e}")
        
        sys.exit(0)
    
    # Create ReasoningEngine instance
    reasoning_engine = reasoning_engines.ReasoningEngine(agent_engine_id)
    print("✅ ReasoningEngine instance created")
    
    # Introspect the object
    print("\n🔍 Available methods on ReasoningEngine:")
    methods = [method for method in dir(reasoning_engine) if not method.startswith('_')]
    for method in sorted(methods):
        attr = getattr(reasoning_engine, method)
        if callable(attr):
            print(f"  📞 {method}() - callable method")
        else:
            print(f"  📝 {method} - property/attribute")
    
    print(f"\n📊 Total public methods: {len([m for m in methods if callable(getattr(reasoning_engine, m))])}")
    print(f"📊 Total public attributes: {len([m for m in methods if not callable(getattr(reasoning_engine, m))])}")
    
    # Try to get help on the object
    print(f"\n📚 ReasoningEngine type: {type(reasoning_engine)}")
    print(f"📚 ReasoningEngine MRO: {type(reasoning_engine).__mro__}")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure google-cloud-aiplatform is installed")
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"Error type: {type(e).__name__}")