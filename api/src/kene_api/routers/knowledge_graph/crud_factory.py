"""Generic CRUD endpoint implementations for knowledge graph nodes.

Provides reusable endpoint logic following the Generic Base Class + Inheritance pattern.
This module eliminates code duplication across 28 node types by extracting common CRUD patterns.
"""

import logging
from collections.abc import Callable
from typing import TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel

from ...auth.models import UserContext
from ...constants import NODE_TYPE_REGISTRY
from ...exceptions import (
    DuplicateNodeException,
    GraphSyncException,
    NodeCreationException,
    NodeHasDependenciesException,
    NodeNotFoundException,
    ValidationException,
)
from ...models.graph_models import DeleteResponse
from ...services.graph_sync_service import GraphSyncService

logger = logging.getLogger(__name__)

# Type variables for generic typing
CreateModel = TypeVar("CreateModel", bound=BaseModel)
UpdateModel = TypeVar("UpdateModel", bound=BaseModel)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
ListResponseModel = TypeVar("ListResponseModel", bound=BaseModel)


async def check_graph_access(
    account_id: str,
    user: UserContext,
    required_level: str = "view",
) -> UserContext:
    """Check if user has required access level for graph operations.

    Args:
        account_id: Account ID to check access for
        user: Current user context
        required_level: Required permission level (view or edit)

    Returns:
        User context if access granted

    Raises:
        HTTPException: If access denied
    """
    # Super admins always have access
    if user.is_super_admin:
        return user

    # Check if user has org admin/owner access (grants access to ALL accounts)
    has_org_admin = any(
        role in ["admin", "owner"] for role in user.organization_permissions.values()
    )
    if has_org_admin:
        logger.info(
            f"[check_graph_access] Access granted via org admin for user {user.email}"
        )
        return user

    # For non-admin users, check account-specific permissions
    if required_level == "edit":
        # Edit requires explicit "edit" role
        if not user.has_account_access(account_id, ["edit"]):
            logger.warning(
                f"[check_graph_access] Edit access denied for user {user.email} to account {account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for edit access to account {account_id}",
            )
    else:
        # View access: just check if account is accessible
        if not user.has_account_access(account_id) and not user.is_super_admin:
            logger.warning(
                f"[check_graph_access] View access denied for user {user.email} to account {account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to account {account_id}",
            )

    logger.info(
        f"[check_graph_access] Access granted for user {user.email} to account {account_id}"
    )
    return user


class CRUDEndpoints:
    """Generic CRUD endpoint implementations for knowledge graph nodes.

    Provides reusable create, read, update, delete, and list operations
    that work for all 28 node types with consistent error handling.
    """

    @staticmethod
    async def create_node(
        account_id: str,
        node_type: str,
        create_data: CreateModel,
        service_method: Callable,
        service: GraphSyncService,
        user: UserContext,
    ) -> ResponseModel:
        """Generic CREATE endpoint implementation.

        Args:
            account_id: Account identifier
            node_type: Node type from NODE_TYPE_REGISTRY
            create_data: Pydantic create model instance
            service_method: Service method to call (e.g., service.create_goal)
            service: GraphSyncService instance
            user: Authenticated user context

        Returns:
            Response model instance (returned directly from service)

        Raises:
            HTTPException: With appropriate status codes
        """
        await check_graph_access(account_id, user, "edit")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            # Service methods always return Response objects (verified in all 28 node types)
            return await service_method(account_id, create_data, user.user_id)
        except ValidationException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except DuplicateNodeException as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except NodeNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except NodeCreationException as e:
            logger.error(f"Node creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            ) from e
        except GraphSyncException as e:
            logger.error(f"Graph sync error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            ) from e
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(
                f"Unexpected error creating {config['human_readable']}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create {config['human_readable']}",
            ) from e

    @staticmethod
    async def list_nodes(
        account_id: str,
        node_type: str,
        response_model_class: type[ResponseModel],
        list_response_class: type[ListResponseModel],
        skip: int,
        limit: int | None,
        service: GraphSyncService,
        user: UserContext,
        parent_filter_id: str | None = None,
        parent_node_type: str | None = None,
    ) -> ListResponseModel:
        """Generic LIST endpoint implementation.

        Handles pagination and optional parent filtering.

        Args:
            account_id: Account identifier
            node_type: Node type from NODE_TYPE_REGISTRY
            response_model_class: Response model class for list items
            list_response_class: List response model class
            skip: Number of items to skip for pagination
            limit: Maximum number of items to return
            service: GraphSyncService instance
            user: Authenticated user context
            parent_filter_id: Optional parent node ID for filtering
            parent_node_type: Optional parent node type for filtering

        Returns:
            List response model instance

        Raises:
            HTTPException: With appropriate status codes
        """
        await check_graph_access(account_id, user, "view")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            # Get total count
            total_count = await service.count_nodes(
                account_id,
                config["neo4j_label"],
                parent_node_id=parent_filter_id,
                parent_node_type=parent_node_type,
            )

            # Get paginated results
            nodes_data = await service.list_nodes(
                account_id,
                config["neo4j_label"],
                skip=skip,
                limit=limit,
                parent_node_id=parent_filter_id,
                parent_node_type=parent_node_type,
            )

            nodes = [response_model_class(**node) for node in nodes_data]

            # Construct list response dynamically
            return list_response_class(
                **{config["list_field_name"]: nodes, "total_count": total_count}
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Failed to list {config['list_field_name']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list {config['list_field_name']}",
            ) from e

    @staticmethod
    async def get_node(
        account_id: str,
        node_id: str,
        node_type: str,
        response_model_class: type[ResponseModel],
        service: GraphSyncService,
        user: UserContext,
    ) -> ResponseModel:
        """Generic GET endpoint implementation.

        Args:
            account_id: Account identifier
            node_id: Node identifier
            node_type: Node type from NODE_TYPE_REGISTRY
            response_model_class: Response model class
            service: GraphSyncService instance
            user: Authenticated user context

        Returns:
            Response model instance

        Raises:
            HTTPException: With appropriate status codes
        """
        await check_graph_access(account_id, user, "view")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            node = await service.get_node(account_id, node_id, config["neo4j_label"])
            if not node:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{config['human_readable'].capitalize()} not found",
                )
            return response_model_class(**node)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Failed to get {config['human_readable']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get {config['human_readable']}",
            ) from e

    @staticmethod
    async def update_node(
        account_id: str,
        node_id: str,
        node_type: str,
        update_data: UpdateModel,
        service_method: Callable,
        service: GraphSyncService,
        user: UserContext,
    ) -> ResponseModel:
        """Generic UPDATE endpoint implementation.

        Args:
            account_id: Account identifier
            node_id: Node identifier
            node_type: Node type from NODE_TYPE_REGISTRY
            update_data: Pydantic update model instance
            service_method: Service method to call (e.g., service.update_goal)
            service: GraphSyncService instance
            user: Authenticated user context

        Returns:
            Response model instance (returned directly from service)

        Raises:
            HTTPException: With appropriate status codes
        """
        await check_graph_access(account_id, user, "edit")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            # Service methods always return Response objects (verified in all 28 node types)
            return await service_method(account_id, node_id, update_data, user.user_id)
        except ValidationException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except DuplicateNodeException as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except NodeNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except GraphSyncException as e:
            logger.error(f"Graph sync error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            ) from e
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(
                f"Unexpected error updating {config['human_readable']}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update {config['human_readable']}",
            ) from e

    @staticmethod
    async def delete_node(
        account_id: str,
        node_id: str,
        node_type: str,
        service_method: Callable,
        service: GraphSyncService,
        user: UserContext,
    ) -> DeleteResponse:
        """Generic DELETE endpoint implementation.

        Args:
            account_id: Account identifier
            node_id: Node identifier
            node_type: Node type from NODE_TYPE_REGISTRY
            service_method: Service method to call (e.g., service.delete_goal)
            service: GraphSyncService instance
            user: Authenticated user context

        Returns:
            DeleteResponse with success status

        Raises:
            HTTPException: With appropriate status codes
        """
        await check_graph_access(account_id, user, "edit")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            await service_method(account_id, node_id, user.user_id)
            return DeleteResponse(
                success=True,
                message=f"{config['human_readable'].capitalize()} {node_id} deleted successfully",
                deleted_node_id=node_id,
            )
        except NodeHasDependenciesException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except NodeNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except GraphSyncException as e:
            logger.error(f"Graph sync error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            ) from e
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(
                f"Unexpected error deleting {config['human_readable']}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete {config['human_readable']}",
            ) from e

    @staticmethod
    async def get_node_with_relationship(
        account_id: str,
        node_id: str,
        node_type: str,
        relationship_query: str,
        relationship_field: str,
        response_model_class: type[ResponseModel],
        service: GraphSyncService,
        user: UserContext,
    ) -> ResponseModel:
        """Get node and populate a field from a relationship query.

        Used by Opportunity/Risk to fetch parent relationship.

        Args:
            account_id: Account identifier
            node_id: Node identifier
            node_type: Node type from NODE_TYPE_REGISTRY
            relationship_query: Cypher query to fetch relationship (must include $node_id parameter)
            relationship_field: Field name to populate in response
            response_model_class: Response model class
            service: GraphSyncService instance
            user: Authenticated user context

        Returns:
            Response model with relationship field populated

        Raises:
            HTTPException: With appropriate status codes
        """
        await check_graph_access(account_id, user, "view")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            node = await service.get_node(account_id, node_id, config["neo4j_label"])
            if not node:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{config['human_readable'].capitalize()} not found",
                )

            # Execute relationship query
            result = await service.neo4j.execute_query(
                relationship_query, {"node_id": node_id}
            )
            if result and result[0]:
                node[relationship_field] = result[0][relationship_field]

            return response_model_class(**node)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Failed to get {config['human_readable']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get {config['human_readable']}",
            ) from e
