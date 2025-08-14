import typing

import pydantic
from mcp.server.fastmcp import FastMCP, Context

DEFAULT_PORT = 8000


class ClickupCustomField(pydantic.BaseModel):
    id: str
    value: str | int


def setup_server():
    from clickup import ClickupClient

    mcp = FastMCP('Clickup MCP Server', stateless_http=True, json_response=True, port=DEFAULT_PORT)

    @mcp.tool()
    async def get_workspaces(
            ctx: Context,
    ):
        """Get a list of all ClickUp workspaces (teams) accessible to the authenticated user.
        Returns workspace IDs, names, and metadata."""
        return await ClickupClient.api_get(ctx.request_context.request, '/team')

    @mcp.tool()
    async def get_spaces(
            ctx: Context,
            workspace_id: typing.Annotated[str, 'The parent workspace id']
    ):
        """Get spaces from a ClickUp workspace. Returns space details including name, settings, and features."""
        return await ClickupClient.api_get(ctx.request_context.request, f'/team/{workspace_id}/space')

    @mcp.tool()
    async def get_lists(
            ctx: Context,
            container_id: typing.Annotated[str, 'The ID of the container to get lists from'],
            container_type: typing.Annotated[
                typing.Literal['folder', 'space'], 'The type of container to get lists from'] = 'space'
    ):
        """Get lists from a ClickUp folder or space. Returns list details including name and content."""
        url = f'/folder/{container_id}/list' if container_type == 'folder' else f'/space/{container_id}/list'
        return await ClickupClient.api_get(ctx.request_context.request, url)

    @mcp.tool()
    async def get_tasks(
            ctx: Context,
            list_id: typing.Annotated[str, 'The ID of the list to get tasks from'],
            include_closed: typing.Annotated[bool, 'Whether to include closed tasks'] = False,
            subtasks: typing.Annotated[bool, 'Whether to include subtasks in the results'] = False,
            page: typing.Annotated[int, 'The page number to get'] = 0,
            order_by: typing.Annotated[str, 'The field to order by'] = None,
            reverse: typing.Annotated[bool, 'Whether to reverse the order'] = False,
    ):
        """Get tasks from a ClickUp list. Returns task details including name, description, assignees, and status."""
        return await ClickupClient.api_get(ctx.request_context.request, f'/list/{list_id}/task', params={
            'include_closed': include_closed,
            'subtasks': subtasks,
            'page': page,
            'order_by': order_by,
            'reverse': reverse
        })

    @mcp.tool()
    async def create_task(
            ctx: Context,
            list_id: typing.Annotated[str, 'The ID of the list to get tasks from'],
            name: typing.Annotated[str, 'The name of the task'],
            description: typing.Annotated[str, 'The description of the task'] = None,
            assignees: typing.Annotated[typing.List[int], 'The IDs of the users to assign to the task'] = None,
            tags: typing.Annotated[typing.List[str], 'The tags to add to the task'] = None,
            status: typing.Annotated[str, 'The status of the task'] = None,
            priority: typing.Annotated[typing.Literal[1, 2, 3, 4], 'The priority of the task (1-4)'] = None,
            notify_all: typing.Annotated[bool, 'Whether to notify all assignees'] = False,
            parent: typing.Annotated[str, 'The ID of the parent task'] = None,
            custom_fields: typing.Annotated[
                typing.List[ClickupCustomField], 'The custom fields to set in this task'] = None
    ):
        """Create a new task in a ClickUp list with specified properties
        like name, description, assignees, status, and dates."""
        data: typing.Dict[str, typing.Any] = {
            'name': name,
            'description': description,
            'assignees': assignees,
            'tags': tags,
            'status': status,
            'notify_all': notify_all,
            'custom_fields': custom_fields
        }
        if priority:
            data['priority'] = priority
        if parent:
            data['parent'] = parent

        return await ClickupClient.api_post(ctx.request_context.request, f'/list/{list_id}/task', data=data)

    @mcp.tool()
    async def get_custom_fields(
            ctx: Context,
            container_id: typing.Annotated[str, 'The ID of the container to get custom fields from'],
            container_type: typing.Annotated[
                typing.Literal['folder', 'list', 'space', 'team'], 'The type of container to get custom fields from']
            = 'space'
    ):
        """Get the defined custom fields from a ClickUp folder, list, space or team/workspace.
        Returns details including id and name."""
        match container_type:
            case 'folder':
                url = f'/folder/{container_id}/field'
            case 'list':
                url = f'/list/{container_id}/field'
            case 'team':
                url = f'/team/{container_id}/field'
            case _:
                url = f'/space/{container_id}/field'
        return await ClickupClient.api_get(ctx.request_context.request, url)

    return mcp
