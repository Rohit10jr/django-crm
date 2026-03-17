from celery import Celery
# from config.celery import app
# from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from common.models import Profile
from opportunity.models import Opportunity

app = Celery("redis://") # [!!] check redis URL


@app.task
# @shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3})
def send_email_to_assigned_user(recipients, opportunity_id):
    """Send Mail To Users When they are assigned to a opportunity"""
    opportunity = Opportunity.objects.get(id=opportunity_id)
    # opportunity = Opportunity.objects.filter(id=opportunity_id).first()
    created_by = opportunity.created_by
    for user in recipients:
        recipients_list = [] # [!!] check if this should be inside loop
        profile = Profile.objects.filter(id=user, is_active=True).first()
        # profiles = Profile.objects.filter(
        #     id__in=recipients,
        #     is_active=True
        # ).select_related("user")

        if profile:
            recipients_list.append(profile.user.email)
            context = {}
            context["url"] = settings.DOMAIN_NAME
            context["user"] = profile.user
            context["opportunity"] = opportunity
            context["created_by"] = created_by
            subject = "Assigned an opportunity for you."
            html_content = render_to_string(
                "assigned_to/opportunity_assigned.html", context=context
            )

            msg = EmailMessage(subject, html_content, to=recipients_list)
            msg.content_subtype = "html"
            msg.send()



#  -----------------------------------------------------------

#  !! check which version to keep   

# from celery import shared_task
# from django.conf import settings
# from django.core.mail import EmailMessage
# from django.template.loader import render_to_string
# from common.models import Profile
# from opportunity.models import Opportunity


# @shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, retry_kwargs={"max_retries": 3})
# def send_email_to_assigned_user(self, recipients, opportunity_id):
#     opportunity = Opportunity.objects.filter(id=opportunity_id).first()
#     if not opportunity:
#         return

#     profiles = Profile.objects.filter(
#         id__in=recipients,
#         is_active=True
#     ).select_related("user")

#     for profile in profiles:
#         context = {
#             "url": settings.DOMAIN_NAME,
#             "user": profile.user,
#             "opportunity": opportunity,
#             "created_by": opportunity.created_by,
#         }

#         html_content = render_to_string(
#             "assigned_to/opportunity_assigned.html", context
#         )

#         msg = EmailMessage(
#             subject=f"You've been assigned: {opportunity.name}",
#             body=html_content,
#             to=[profile.user.email],
#         )
#         msg.content_subtype = "html"
#         msg.send()
