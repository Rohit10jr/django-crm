from datetime import datetime, timedelta

from django.test import TestCase 
from django.test.utils import override_settings

from contacts.tasks import send_email_to_assigned_user
# [!!] does not exist
# from contacts.tests import ContactObjectsCreation


# [??] why have similar test in every app 
# [!!]class TestCeleryTasks(TestCase): use this
class TestCeleryTasks(ContactObjectsCreation, TestCase):
    @override_settings(
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
        CELERY_ALWAYS_EAGER=True,
        BROKER_BACKEND="memory",
    )
    def test_celery_tasks(self):
        task = send_email_to_assigned_user.apply(
            (
                [
                    self.user.id,
                    self.user_contacts_mp.id,
                ],
                self.contact.id,
            ),
        )
        self.assertEqual("SUCCESS", task.state)
