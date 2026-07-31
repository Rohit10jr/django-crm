# Fork backend annotations — [??] and [!!] markers

Extracted before upstream adoption overwrites backend/. 226 occurrences across 49 files.
Format: path:line: annotation text

backend/accounts/models.py:133:    # [??] maybe add the logic in clean
backend/accounts/models.py:144:                # [??] recipients is missing, need to add it back to the model to make this work ?
backend/accounts/models.py:189:            # [!!]  contact is missing
backend/accounts/models.py:98:        # [??] contacts is missing, need to add it back to the model to make this work ?
backend/accounts/serializer.py:122:        # [!!] contact is missing in AccountEmailLog
backend/accounts/serializer.py:137:        # [!!] contacts is missing in Account
backend/accounts/serializer.py:14:# [!!] rename TagsSerializer
backend/accounts/serializer.py:20:# [??] use select_related() prefetch_related()
backend/accounts/serializer.py:218:        # [!!] recipients is missing in AccountEmail
backend/accounts/serializer.py:29:    # [!!] serial
backend/accounts/serializer.py:62:            # [!!] no contacts
backend/accounts/serializer.py:83:    # [!!] redundant
backend/accounts/tasks.py:118:# [!!] better logic for last task
backend/accounts/tasks.py:66:    # [??] from_email is misleading, find and change it to appropriate name
backend/accounts/tasks.py:72:        # [??] check Profile.objects.filter(id__in=recipients)
backend/accounts/tasks.py:97:        # [??] compare timezone vs datetimte
backend/accounts/views.py:149:        # [!!] duplicate
backend/accounts/views.py:174:                # [!!] contacts = request.data.get("contacts", [])
backend/accounts/views.py:188:                        # [!!] above condition checks with lower
backend/accounts/views.py:189:                        # [!!] but here saved with same tag name, causes mismatch in filtering with tags, better to save with lower case name or slug field
backend/accounts/views.py:246:        # [!!] org filter is handled in get_object 
backend/accounts/views.py:341:        # [!!] org filter is handled in get_object 
backend/accounts/views.py:365:        # [!!] org filter is handled in get_object 
backend/accounts/views.py:373:        # [!!] use this seperate permission check class
backend/accounts/views.py:374:        # [!!] add this before context
backend/accounts/views.py:539:    # [??] no use of this 
backend/accounts/views.py:541:    # [!!] use get_object_or_404
backend/accounts/views.py:559:            # [!!] this comment logic is not required
backend/accounts/views.py:649:        # [!!] this code overwrites the original request data
backend/accounts/views.py:662:                # [??] Contact.objects.filter(id__in=contacts)
backend/accounts/views.py:679:                # [??] save is missing
backend/accounts/views.py:67:        # [??] what happens if this fails
backend/cases/serializer.py:45:    # [!!] missing parentheses and might be dead code, check and remove if not required
backend/cases/solution_serializers.py:43:        # [!!] this query an cause N+1 queries in list APIs, use annotate in queryset to optimize this.
backend/cases/solution_serializers.py:96:        # [!!] prefetch_related("cases") in queryset can optimize this to avoid N+1 queries
backend/cases/solution_views.py:104:        # [!!] get_object_or_404
backend/cases/views.py:188:        # [!!] redundant logic, org filter is applied in get_object 
backend/cases/views.py:273:        # [!!] redundant logic, org filter is applied in get_object
backend/cases/views.py:302:        # [!!] redundant logic, org filter is applied in get_object
backend/cases/views.py:310:        # [!!] adds this in custom logic
backend/cases/views.py:33:# [??] use select_related(), prefetch_related() for better performance
backend/cases/views.py:380:    # [??] pk is to identify case
backend/cases/views.py:383:        # [??] use get_object here instead of direct query and remove redundant org filter in get_object
backend/cases/views.py:39:    # [??] use get_queryset instead of get_context_data and move filter logic to get_queryset
backend/cases/views.py:405:            # [!!] serializer.is_valid should be enough to check if comment is present or not, remove redundant check
backend/cases/views.py:464:            # [!!] serializer.is_valid is enough
backend/cases/views.py:513:        # [!!] add org filter here
backend/cases/views.py:64:            # [!!] we can optimize this by creating a dict of filter params and passing it to filter method instead of multiple if conditions
backend/cases/views.py:65:            # [??] check how we can implement django-filter here
backend/common/access_decorators_mixins.py:5:# [??] use one central admin logic
backend/common/base.py:41:        # [??] better option
backend/common/base.py:73:            # [??] _state
backend/common/context_processors/common.py:3:# [!!] this is not included in settings.py templates 
backend/common/external_auth.py:24:# [??] assumes one admin per org, may need to be updated if we want multiple admins per org
backend/common/external_auth.py:32:        # [??]
backend/common/management/commands/audit_org_fields.py:169:        # [!!] udpated recommendations based on fix
backend/common/management/commands/audit_org_fields.py:21:    # [??] understand this block 
backend/common/management/commands/audit_org_fields.py:80:                model = apps.get_model(app_label, model_name)  # [??]
backend/common/management/commands/audit_org_fields.py:81:                total_count = model.objects.count()  # [??] 
backend/common/management/commands/audit_org_fields.py:82:                null_count = model.objects.filter(org__isnull=True).count() # [??]
backend/common/management/commands/audit_org_fields.py:99:                    self._show_model_details(model)  # [??]
backend/common/management/commands/manage_rls.py:106:        self.stdout.write(self.style.MIGRATE_HEADING("Testing RLS...")) # [??]
backend/common/management/commands/manage_rls.py:121:            org_a = str(orgs[0][0]) # [??]
backend/common/management/commands/manage_rls.py:23:    ORG_SCOPED_TABLES = RLS_CONFIG["tables"] # [??] understand this block
backend/common/management/commands/manage_rls.py:54:        self.stdout.write(self.style.MIGRATE_HEADING("RLS Status:")) #[??] understand
backend/common/management/commands/manage_rls.py:62:            user, is_super = cursor.fetchone() # [??]
backend/common/management/commands/manage_rls.py:87:                    rls_enabled, rls_forced = result # [??]
backend/common/management/commands/migrate_from_prisma.py:1016:            # [??]
backend/common/management/commands/migrate_from_prisma.py:1130:# [??] check this 
backend/common/management/commands/migrate_from_prisma.py:1143:        # [??]
backend/common/management/commands/migrate_from_prisma.py:1240:            # [??]
backend/common/management/commands/migrate_from_prisma.py:1407:            # [??]
backend/common/management/commands/migrate_from_prisma.py:1483:            # [??]
backend/common/management/commands/migrate_from_prisma.py:1:# [??] understand the config / requirement of prisma
backend/common/management/commands/migrate_from_prisma.py:332:            name_parts = name.split(" ", 1) # [??] check if name_parts used later
backend/common/management/commands/migrate_from_prisma.py:336:                profile_pic = row["profilePhoto"] # [??] url ?
backend/common/management/commands/migrate_from_prisma.py:422:            # [??] 
backend/common/management/commands/migrate_from_prisma.py:482:                            ),  # Convert to 2-letter code [??] why
backend/common/management/commands/migrate_from_prisma.py:494:                # [??]
backend/common/management/commands/migrate_from_prisma.py:641:            # [??]
backend/common/management/commands/migrate_from_prisma.py:724:            # [??]
backend/common/management/commands/migrate_from_prisma.py:761:                # [!!] m2m core table data
backend/common/management/commands/migrate_from_prisma.py:779:        # [??] why we doing this
backend/common/management/commands/migrate_from_prisma.py:792:        # [??] why no skip options
backend/common/management/commands/migrate_from_prisma.py:793:        # [!!] migrate_oppportunity_contacts() = relationship table
backend/common/management/commands/migrate_from_prisma.py:838:            # [??]
backend/common/management/commands/migrate_from_prisma.py:851:                # [??]
backend/common/management/commands/migrate_from_prisma.py:980:        # [??] why no skip
backend/common/management/commands/migrate_from_prisma.py:981:        # [!!] no skip because this just handles m2m
backend/common/middleware/get_company.py:16:# [??] not used here
backend/common/models.py:133:                # [??] get_country_display missing
backend/common/models.py:301:    # [??] add them for target models
backend/common/models.py:318:        # [??] 
backend/common/models.py:366:            # [??]
backend/common/models.py:664:    # [??] try genericforeign key
backend/common/models.py:682:        # [??] what is get_action_display
backend/common/models.py:715:        # [??]
backend/common/models.py:798:# [??] why this here
backend/common/models.py:95:    # [??] same but with simplier code  
backend/common/permissions.py:236:        # [??] return False
backend/common/serializer.py:598:    # [??] get_action_display missing in model
backend/common/serializer.py:670:            # [??] following are for get request
backend/common/serializer.py:87:    # [!!] object_id not object_id
backend/common/tasks.py:18:# [!!] app = Celery("redis://")
backend/common/tasks.py:211:                # [??] what is this html_context
backend/common/tasks.py:217:            # [!!] send
backend/common/tasks.py:258:        # [??] above is bug
backend/common/tasks.py:278:    # [!!] avoid crashing
backend/common/tasks.py:286:    # [??] why token is added in context again
backend/common/tasks.py:317:    # [??] removed_users is missing, should be removed_users_list
backend/common/tasks.py:39:# [!!] task re-try option 
backend/common/templatetags/common_tags.py:585:    # [!!] lower it
backend/common/templatetags/common_tags.py:5:# [??] i think org repo has not added the register to all the func
backend/common/templatetags/common_tags.py:613:    # [!!] check how to use prefetch, this causes DB query per template render
backend/common/token_generator.py:8:    # [!!] indentation error
backend/common/urls.py:47:# [??] why urls are commented?
backend/common/utils.py:17:        # [??] what is file_prepend ?
backend/contacts/models.py:56:    # [??] this field is required for generic relation to work on serializer
backend/contacts/models.py:71:        # [??] models.UniqueConstraint for email and org
backend/contacts/serializer.py:11:# [!!] find about contact_attachment
backend/contacts/swagger_params.py:50:# [!!] updated swagger params
backend/contacts/tasks.py:11:# [??] why have same task in almost every app
backend/contacts/tests_celery_tasks.py:11:# [??] why have similar test in every app 
backend/contacts/tests_celery_tasks.py:12:# [!!]class TestCeleryTasks(TestCase): use this
backend/contacts/tests_celery_tasks.py:7:# [!!] does not exist
backend/contacts/views.py:107:        # [!!] how about this, serializer.save(org=request.profile.org)
backend/contacts/views.py:134:            # [??] attachment doesnt have contact field
backend/contacts/views.py:139:            # [!!] correct by Attachments model fields 
backend/contacts/views.py:171:        # [!!] redundant org check 
backend/contacts/views.py:214:        # [!!] this is should come above code block
backend/contacts/views.py:24:# [??] can we use GenericAPIView + ListCreateAPIView
backend/contacts/views.py:250:        # [!!] account_contacts is reverse relation to Account model
backend/contacts/views.py:251:        # [??] but that field is commented
backend/contacts/views.py:25:# [!!] the serializer has contact_attachment field, view doesnt add nor the model has it 
backend/contacts/views.py:286:        # [??] redundant code, no use of user_assgn_list after checking above condition 
backend/contacts/views.py:326:        # [!!] redundant logic, we use org in queryset itself.
backend/contacts/views.py:344:        # [!!] contact model doesnt have address_id field nor reverse relation for address_id.  
backend/contacts/views.py:361:        # [!!] missing org check
backend/contacts/views.py:379:                    # [!!] these fields dont exist
backend/contacts/views.py:389:            # [!!] this doenst have contact relation
backend/contacts/views.py:476:# [!!] the admin logic is used everywhere, add them inside custom permission.
backend/contacts/views.py:47:                # [!!] city_icontains not address__city__icontains
backend/contacts/views.py:485:        # [??] attachment model has org field 
backend/contacts/views.py:486:        # [!!] can we add org=request.profile.org in this query
backend/invoices/api_views.py:125:        # [!!] request.user.role == "ADMIN" ?
backend/invoices/api_views.py:161:            # [!!] wrong arguments, please check
backend/invoices/api_views.py:171:            # [!!] instead of overriding fields here use source in serializers or get fields together and then save it
backend/invoices/api_views.py:192:                # [??] is this quality? or quantity?
backend/invoices/api_views.py:309:            # [!!] wrong arguments, please check
backend/invoices/api_views.py:414:        # [!!] CASCADE can do this, so why this? 
backend/invoices/api_views.py:51:# [!!] use DRF inbuilt pagination classes
backend/invoices/api_views.py:578:        # [!!] use get_object_or_404
backend/invoices/api_views.py:589:        # [!!] use this seperate permission check class
backend/invoices/api_views.py:590:        # [!!] this is repeated in multiple views
backend/invoices/api_views.py:71:            # [??] if we get multiple params, does it filter any?
backend/invoices/api_views.py:80:            # [??] getlist or get in this case
backend/invoices/forms.py:92:    # [??] task comes from?
backend/invoices/models.py:13:# [!!] add INVOICE_STATUS choices to common utils later
backend/invoices/serializer.py:80:        # [!!] invoice_view is redundant currently
backend/invoices/serializer.py:89:            # [!!] Implement DRY
backend/invoices/tasks.py:133:    # [!!] add this condition above so that we can skip computing when dont have to create history for created invoice
backend/invoices/tasks.py:20:    # [!!] query inside loops is not sound choice because it will hit the database multiple times.
backend/invoices/tasks.py:36:                # [??] Check this. Invoice URL namespace is, app_name=api_invoices
backend/invoices/tasks.py:46:    # [??]  check the logic of this filter
backend/invoices/tasks.py:75:# [!!] check if we can combine send_invoice_email and send_invoice_email_cancel into one function with an extra parameter
backend/invoices/tasks.py:76:# [!!] try to use request.build_absolute_uri() or set BASE_URL in settings
backend/leads/forms.py:75:    # [!!] add widgets in field definition
backend/leads/forms.py:89:        # [??] redundant code? same logic in two places
backend/leads/serializer.py:106:        # [!!] maybe use context inistead of pop 
backend/leads/swagger_params.py:4:# [!!] bug
backend/leads/tests_celery_tasks.py:10:# [??] missing imports
backend/leads/views.py:1050:    # [!!] no validation to check if company is realted to user
backend/leads/views.py:1057:            # [??] Http404 import was missing
backend/leads/views.py:169:        # [!!] send request as context
backend/leads/views.py:181:                        # [!!] use first in filter instead of this
backend/leads/views.py:191:                # [!!] check if ** instead of *
backend/leads/views.py:211:                # [!!] check if ** instead of *
backend/leads/views.py:242:                # [!!] after assigning to objects we need account_object.save()
backend/leads/views.py:306:        # [!!] better option -> 
backend/leads/views.py:308:        # [!!] and why add user object when user_assgn_list contains only id's
backend/leads/views.py:312:            # [!!] code adds user object and now checks for id, wrong logic
backend/leads/views.py:329:        # [!!] for nested dict i think we can use values()
backend/leads/views.py:370:        # [!!] why in two places 
backend/leads/views.py:427:        # [!!] use get_object_or_404
backend/leads/views.py:459:                # [!!] why not use request.user
backend/leads/views.py:516:            # [!!] replacement for below condition
backend/leads/views.py:530:            # [!!] remove this from here
backend/leads/views.py:534:            # [!!] place this logic after the if params.get("assigned_to"): condition
backend/leads/views.py:549:            # [!!] use this condition if "tags" in params:
backend/leads/views.py:554:                # [!!] * is missing *obj_contact)
backend/leads/views.py:74:                    # [!!] should be | instead of & 
backend/opportunity/models.py:12:# [??] AssignableMixin
backend/opportunity/serializer.py:87:        request_obj = kwargs.pop("request_obj", None) # [!!] request_obj is the request object and update it to context
backend/opportunity/serializer.py:88:        # [!!] request = self.context.get("request")
backend/opportunity/swagger_params.py:13:# [!!] use organization_params
backend/opportunity/swagger_params.py:4:# [!!] usesless double assignment
backend/opportunity/tasks.py:11:app = Celery("redis://") # [!!] check redis URL
backend/opportunity/tasks.py:22:        recipients_list = [] # [!!] check if this should be inside loop
backend/opportunity/views.py:136:    # [!!] maybe create service/OpportunityService to handle business logic and call it from views.
backend/opportunity/views.py:192:                # [!!] Why created_by is set to user instead of profile, 
backend/opportunity/views.py:193:                # [!!] also both these fields are missing in attachments and base model
backend/opportunity/views.py:251:        # [!!] use context to send the request
backend/opportunity/views.py:30:# [!!] use @transaction.atomic for model creation and trigger celery task
backend/opportunity/views.py:527:            # [!!] the params logic is redundant as validation checks if the comment field exists or not in serializer
backend/opportunity/views.py:56:    model = Opportunity # [!!] APIView does not have model attribute by default
backend/opportunity/views.py:58:    # [!!] use get_opportunity_list_data as method name
backend/opportunity/views.py:96:        # [!!] why not use drf get_paginated_response instead of manually paginating and creating response
backend/tasks/models.py:68:        # [!!] better option is constraints than unique_together
backend/tasks/serializer.py:170:        # [!!] use context that is DRF way.
backend/tasks/swagger_params.py:26:    # [!!] dont use this here
backend/tasks/swagger_params.py:4:# [!!] usesless double assignment
backend/tasks/views.py:180:        # [!!] add this in custom logic
backend/tasks/views.py:225:        # [!!] redundant logic
backend/tasks/views.py:293:            # [!!] these fields are missing and attachment.task is not in model
backend/tasks/views.py:299:            # [!!] basemodel already sets this created_by
backend/tasks/views.py:306:        # [!!] since we dont set content_type = Task, object_id = task.id
backend/tasks/views.py:307:        # [!!] this might fail
backend/tasks/views.py:343:            # [!!] not used
backend/tasks/views.py:403:        # [!!] use get_object_or_404
backend/tasks/views.py:421:                # [!!] use raise_exception=True instead of this check
backend/tasks/views.py:470:        # [!!] add org=request.profile.org in this query
backend/tasks/views.py:50:        # [!!] this can cause n+1 problem
backend/tasks/views.py:547:        # [!!] offset is handled internally, update pervious pagination like this.
backend/tasks/views.py:54:        # [!!] this solves n+1 problem
backend/tasks/views.py:574:        # [!!] .copy() is used to make request.data mutable
backend/tasks/views.py:93:        # [!!] manual offset risky
