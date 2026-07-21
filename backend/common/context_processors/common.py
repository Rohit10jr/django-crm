from django.conf import settings

# [!!] this is not included in settings.py templates 
def app_name(request):
    return {
        "APPLICATION_NAME": settings.APPLICATION_NAME,
    }
