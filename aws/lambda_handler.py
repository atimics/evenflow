"""
AWS Lambda handler for Evenflow MCP server.

This module provides the Lambda entry point for running the MCP server
on AWS Lambda with API Gateway or direct invocation.

Deployment:
    1. Package with dependencies: pip install -t ./package -r requirements-lambda.txt
    2. Create ZIP: cd package && zip -r ../deployment.zip . && cd .. && zip deployment.zip lambda_handler.py
    3. Deploy to Lambda with Python 3.11 runtime
"""

import json
import os
import sys
from typing import Any, Dict

# Add the project root to the path
# In Lambda, the handler file is at the root of the deployment package
lambda_root = os.path.dirname(os.path.abspath(__file__))
if lambda_root not in sys.path:
    sys.path.insert(0, lambda_root)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point for MCP server.
    
    Supports two invocation modes:
    1. Direct invocation: Pass MCP JSON-RPC request in event body
    2. API Gateway: HTTP request with MCP JSON-RPC in body
    
    Args:
        event: Lambda event (API Gateway or direct invocation)
        context: Lambda context object
        
    Returns:
        API Gateway response or direct MCP response
    """
    # Lazy import to reduce cold start time
    from mcp.server import create_server
    from mcp.world_adapter import get_adapter
    
    # Initialize adapter (connection pooling across invocations)
    adapter = get_adapter()
    
    # Parse request body
    body = event.get("body", event)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON in request body")
    
    # Handle MCP JSON-RPC request
    try:
        mcp = create_server()
        
        # Route to appropriate handler based on method
        method = body.get("method", "")
        params = body.get("params", {})
        request_id = body.get("id", 1)
        
        if method.startswith("tools/"):
            result = _handle_tool_call(mcp, method, params)
        elif method.startswith("resources/"):
            result = _handle_resource_read(mcp, method, params)
        elif method == "initialize":
            result = _handle_initialize(mcp)
        elif method == "tools/list":
            result = _handle_list_tools(mcp)
        elif method == "resources/list":
            result = _handle_list_resources(mcp)
        else:
            return _error_response(400, f"Unknown method: {method}")
        
        response_body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }
        
    except Exception as e:
        return _error_response(500, str(e))
    
    # Format for API Gateway if needed
    if "requestContext" in event:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }
    
    return response_body


def _handle_initialize(mcp) -> Dict[str, Any]:
    """Handle MCP initialize request."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"listChanged": False, "subscribe": False},
        },
        "serverInfo": {
            "name": "evenflow-mcp",
            "version": "0.1.0",
        },
    }


def _handle_list_tools(mcp) -> Dict[str, Any]:
    """Handle tools/list request."""
    # Tool definitions
    tools = [
        {
            "name": "get_location_state",
            "description": "Get the current state of a location including affinity traces and affordances.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "The unique identifier of the location"},
                    "include_traces": {"type": "boolean", "default": True},
                    "include_affordances": {"type": "boolean", "default": True},
                },
                "required": ["location_id"],
            },
        },
        {
            "name": "list_locations",
            "description": "List all available location IDs in the world.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "compute_affinity",
            "description": "Compute the affinity score for an actor at a specific location.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "location_id": {"type": "string"},
                    "actor_id": {"type": "string"},
                    "actor_tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["location_id", "actor_id", "actor_tags"],
            },
        },
        {
            "name": "query_traces",
            "description": "Query affinity traces across the world.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "location_id": {"type": "string"},
                    "actor_id": {"type": "string"},
                    "event_type": {"type": "string"},
                    "channel": {"type": "string", "enum": ["personal", "group", "behavior"]},
                    "min_intensity": {"type": "number", "default": 0.0},
                    "limit": {"type": "integer", "default": 100},
                },
            },
        },
        {
            "name": "predict_action",
            "description": "Predict the consequences of an action without actually performing it.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "actor_id": {"type": "string"},
                    "actor_tags": {"type": "array", "items": {"type": "string"}},
                    "location_id": {"type": "string"},
                    "event_type": {"type": "string"},
                    "intensity": {"type": "number"},
                },
                "required": ["actor_id", "actor_tags", "location_id", "event_type", "intensity"],
            },
        },
        {
            "name": "get_world_history",
            "description": "Get a summary of recent world history for folklore generation.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "location_id": {"type": "string"},
                    "time_window_days": {"type": "integer", "default": 30},
                },
                "required": ["location_id"],
            },
        },
        {
            "name": "get_affordance_registry",
            "description": "Get the global affordance registry showing which affordances are enabled.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "export_world_state",
            "description": "Export the complete world state as a JSON snapshot.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "explain_valuation",
            "description": "Explain how a location values a specific event type.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "location_id": {"type": "string"},
                    "event_type": {"type": "string"},
                },
                "required": ["location_id", "event_type"],
            },
        },
    ]
    return {"tools": tools}


def _handle_list_resources(mcp) -> Dict[str, Any]:
    """Handle resources/list request."""
    resources = [
        {
            "uri": "location://{location_id}",
            "name": "Location State",
            "description": "Get a location's complete state as a resource",
            "mimeType": "application/json",
        },
        {
            "uri": "affordance://registry",
            "name": "Affordance Registry",
            "description": "Get the global affordance registry",
            "mimeType": "application/json",
        },
        {
            "uri": "world://state",
            "name": "World State",
            "description": "Get complete world state export",
            "mimeType": "application/json",
        },
        {
            "uri": "config://affinity",
            "name": "Affinity Config",
            "description": "Get the affinity system configuration",
            "mimeType": "application/json",
        },
    ]
    return {"resources": resources}


def _handle_tool_call(mcp, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tools/call request."""
    from mcp.world_adapter import get_adapter
    from mcp.schemas import (
        LocationQuery,
        TraceQuery,
        ActionPrediction,
        DecayChannel,
        to_dict,
    )
    
    adapter = get_adapter()
    tool_name = params.get("name", method.replace("tools/call/", ""))
    arguments = params.get("arguments", {})
    
    # Route to tool implementation
    if tool_name == "get_location_state":
        query = LocationQuery(
            location_id=arguments["location_id"],
            include_traces=arguments.get("include_traces", True),
            include_affordances=arguments.get("include_affordances", True),
        )
        result = adapter.get_location_state(query)
        if result is None:
            return {"content": [{"type": "text", "text": f"Location not found: {arguments['location_id']}"}]}
        return {"content": [{"type": "text", "text": json.dumps(to_dict(result), indent=2)}]}
    
    elif tool_name == "list_locations":
        locations = adapter.list_locations()
        return {"content": [{"type": "text", "text": json.dumps(locations)}]}
    
    elif tool_name == "compute_affinity":
        result = adapter.compute_affinity_for_actor(
            location_id=arguments["location_id"],
            actor_id=arguments["actor_id"],
            actor_tags=set(arguments.get("actor_tags", [])),
        )
        if result is None:
            return {"content": [{"type": "text", "text": f"Location not found: {arguments['location_id']}"}]}
        return {"content": [{"type": "text", "text": json.dumps(to_dict(result), indent=2)}]}
    
    elif tool_name == "query_traces":
        channel_enum = None
        if arguments.get("channel"):
            channel_enum = DecayChannel(arguments["channel"])
        query = TraceQuery(
            location_id=arguments.get("location_id"),
            actor_id=arguments.get("actor_id"),
            event_type=arguments.get("event_type"),
            channel=channel_enum,
            min_intensity=arguments.get("min_intensity", 0.0),
            limit=arguments.get("limit", 100),
        )
        results = adapter.query_traces(query)
        return {"content": [{"type": "text", "text": json.dumps([to_dict(t) for t in results], indent=2)}]}
    
    elif tool_name == "predict_action":
        prediction = ActionPrediction(
            actor_id=arguments["actor_id"],
            actor_tags=arguments["actor_tags"],
            location_id=arguments["location_id"],
            event_type=arguments["event_type"],
            intensity=arguments["intensity"],
        )
        result = adapter.predict_action_consequence(prediction)
        if result is None:
            return {"content": [{"type": "text", "text": f"Location not found: {arguments['location_id']}"}]}
        return {"content": [{"type": "text", "text": json.dumps(to_dict(result), indent=2)}]}
    
    elif tool_name == "get_world_history":
        result = adapter.get_world_history_summary(
            location_id=arguments["location_id"],
            time_window_days=arguments.get("time_window_days", 30),
        )
        if result is None:
            return {"content": [{"type": "text", "text": f"Location not found: {arguments['location_id']}"}]}
        return {"content": [{"type": "text", "text": json.dumps(to_dict(result), indent=2)}]}
    
    elif tool_name == "get_affordance_registry":
        registry = adapter.get_affordance_registry()
        return {"content": [{"type": "text", "text": json.dumps(registry, indent=2)}]}
    
    elif tool_name == "export_world_state":
        state = adapter.export_world_state()
        return {"content": [{"type": "text", "text": json.dumps(state, indent=2)}]}
    
    elif tool_name == "explain_valuation":
        location = adapter.get_location(arguments["location_id"])
        if location is None:
            return {"content": [{"type": "text", "text": f"Location not found: {arguments['location_id']}"}]}
        
        event_type = arguments["event_type"]
        profile = location.valuation_profile
        
        if event_type in profile:
            result = {
                "event_type": event_type,
                "weight": profile[event_type],
                "match_type": "exact",
            }
        else:
            category = event_type.split('.')[0]
            if category in profile:
                result = {
                    "event_type": event_type,
                    "weight": profile[category],
                    "match_type": "category",
                    "category": category,
                }
            else:
                result = {
                    "event_type": event_type,
                    "weight": 0.0,
                    "match_type": "default",
                }
        
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    
    else:
        return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}


def _handle_resource_read(mcp, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle resources/read request."""
    from mcp.world_adapter import get_adapter
    from mcp.schemas import LocationQuery, to_dict
    from world.affinity.config import get_config
    
    adapter = get_adapter()
    uri = params.get("uri", "")
    
    if uri.startswith("location://"):
        location_id = uri.replace("location://", "")
        query = LocationQuery(location_id=location_id)
        result = adapter.get_location_state(query)
        if result is None:
            return {"contents": [{"uri": uri, "mimeType": "application/json", "text": "{}"}]}
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(to_dict(result), indent=2)}]}
    
    elif uri == "affordance://registry":
        registry = adapter.get_affordance_registry()
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(registry, indent=2)}]}
    
    elif uri == "world://state":
        state = adapter.export_world_state()
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(state, indent=2)}]}
    
    elif uri == "config://affinity":
        config = get_config()
        config_dict = {
            "half_lives": {
                "location": {
                    "personal": config.half_lives.location.personal,
                    "group": config.half_lives.location.group,
                    "behavior": config.half_lives.location.behavior,
                },
            },
            "channel_weights": {
                "personal": config.channel_weights.personal,
                "group": config.channel_weights.group,
                "behavior": config.channel_weights.behavior,
            },
        }
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(config_dict, indent=2)}]}
    
    else:
        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f"Unknown resource: {uri}"}]}


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create an error response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": message,
            },
        }),
    }
