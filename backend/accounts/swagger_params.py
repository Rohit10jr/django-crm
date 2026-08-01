from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

organization_params_in_header = organization_params_in_header = OpenApiParameter(
    "org", OpenApiTypes.STR, OpenApiParameter.HEADER
)

organization_params = [
]

account_get_params = [
    OpenApiParameter("name", OpenApiTypes.STR, OpenApiParameter.QUERY),
    OpenApiParameter("city", OpenApiTypes.STR, OpenApiParameter.QUERY),
    OpenApiParameter("tags", OpenApiTypes.STR, OpenApiParameter.QUERY),
]
