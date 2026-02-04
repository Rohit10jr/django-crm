from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

# [!!] usesless double assignment
# organization_params_in_header =
#  organization_params_in_header = organization_params_in_header = OpenApiParameter(

#     "org", OpenApiTypes.STR, OpenApiParameter.HEADER

# )
 
organization_params_in_header = OpenApiParameter(
    name="org",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=True,  # Set to False if the header is optional
    description="The Organization ID for scoping requests"
)

organization_params = [
    organization_params_in_header,
]

task_list_get_params = [
    organization_params
    # [!!] dont use this here
    # organization_params_in_header,
    OpenApiParameter("title", OpenApiTypes.STR, OpenApiParameter.QUERY),
    OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY),
    OpenApiParameter("priority", OpenApiTypes.STR, OpenApiParameter.QUERY),
]
