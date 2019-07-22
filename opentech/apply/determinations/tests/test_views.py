import urllib

from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.urls import reverse_lazy

from opentech.apply.activity.models import Activity
from opentech.apply.determinations.models import ACCEPTED, REJECTED
from opentech.apply.determinations.views import BatchDeterminationCreateView
from opentech.apply.users.tests.factories import StaffFactory, UserFactory
from opentech.apply.funds.models import ApplicationSubmission
from opentech.apply.funds.tests.factories import ApplicationSubmissionFactory
from opentech.apply.utils.testing import BaseViewTestCase

from .factories import DeterminationFactory


class StaffDeterminationsTestCase(BaseViewTestCase):
    user_factory = StaffFactory
    url_name = 'funds:submissions:determinations:{}'
    base_view_name = 'detail'

    def get_kwargs(self, instance):
        return {'submission_pk': instance.submission.id, 'pk': instance.pk}

    def test_can_access_determination(self):
        submission = ApplicationSubmissionFactory(status='in_discussion')
        determination = DeterminationFactory(submission=submission, author=self.user, submitted=True)
        response = self.get_page(determination)
        self.assertContains(response, determination.submission.title)
        self.assertContains(response, self.user.full_name)
        self.assertContains(response, submission.get_absolute_url())

    def test_lead_can_access_determination(self):
        submission = ApplicationSubmissionFactory(status='in_discussion', lead=self.user)
        determination = DeterminationFactory(submission=submission, author=self.user, submitted=True)
        response = self.get_page(determination)
        self.assertContains(response, determination.submission.title)
        self.assertContains(response, self.user.full_name)
        self.assertContains(response, submission.get_absolute_url())


class DeterminationFormTestCase(BaseViewTestCase):
    user_factory = StaffFactory
    url_name = 'funds:submissions:determinations:{}'
    base_view_name = 'detail'

    def get_kwargs(self, instance):
        return {'submission_pk': instance.id, 'pk': instance.determinations.first().id}

    def get_form_kwargs(self, instance):
        return {'submission_pk': instance.id}

    def test_can_access_form_if_lead(self):
        submission = ApplicationSubmissionFactory(status='in_discussion', lead=self.user)
        response = self.get_page(submission, 'form')
        self.assertContains(response, submission.title)
        self.assertContains(response, submission.get_absolute_url())

    def test_cant_access_wrong_status(self):
        submission = ApplicationSubmissionFactory(status='rejected')
        response = self.get_page(submission, 'form')
        self.assertRedirects(response, self.absolute_url(submission.get_absolute_url()))

    def test_cant_resubmit_determination(self):
        submission = ApplicationSubmissionFactory(status='in_discussion', lead=self.user)
        determination = DeterminationFactory(submission=submission, author=self.user, accepted=True, submitted=True)
        response = self.post_page(submission, {'data': 'value', 'outcome': determination.outcome}, 'form')
        self.assertRedirects(response, self.absolute_url(submission.get_absolute_url()))

    def test_can_edit_draft_determination(self):
        submission = ApplicationSubmissionFactory(status='post_review_discussion', lead=self.user)
        DeterminationFactory(submission=submission, author=self.user)
        response = self.post_page(submission, {
            'data': 'value',
            'outcome': ACCEPTED,
            'message': 'Accepted determination draft message',
            'save_draft': True,
        }, 'form')
        self.assertContains(response, '[Draft] Approved')
        self.assertContains(response, self.url(submission, 'form', absolute=False))
        self.assertNotContains(response, 'Accepted determination draft message')

    def test_cant_edit_submitted_more_info(self):
        submission = ApplicationSubmissionFactory(status='in_discussion', lead=self.user)
        DeterminationFactory(submission=submission, author=self.user, submitted=True)
        response = self.get_page(submission, 'form')
        self.assertNotContains(response, 'Update ')

    def test_can_edit_draft_determination_if_not_lead(self):
        submission = ApplicationSubmissionFactory(status='in_discussion')
        determination = DeterminationFactory(submission=submission, author=self.user, accepted=True)
        response = self.post_page(submission, {'data': 'value', 'outcome': determination.outcome}, 'form')
        self.assertContains(response, 'Approved')
        self.assertRedirects(response, self.absolute_url(submission.get_absolute_url()))

    def test_sends_message_if_requires_more_info(self):
        submission = ApplicationSubmissionFactory(status='in_discussion', lead=self.user)
        determination = DeterminationFactory(submission=submission, author=self.user)
        determination_message = 'This is the message'
        self.post_page(
            submission,
            {'data': 'value', 'outcome': determination.outcome, 'message': determination_message},
            'form',
        )
        self.assertEqual(Activity.comments.count(), 1)
        self.assertEqual(Activity.comments.first().message, determination_message)

    def test_can_progress_stage_via_determination(self):
        submission = ApplicationSubmissionFactory(status='concept_review_discussion', workflow_stages=2, lead=self.user)

        response = self.post_page(submission, {
            'data': 'value',
            'outcome': ACCEPTED,
            'message': 'You are invited to submit a proposal',
        }, 'form')

        # Cant use refresh from DB with FSM
        submission_original = self.refresh(submission)
        submission_next = submission_original.next

        # Cannot use self.url() as that uses a different base.
        url = submission_next.get_absolute_url()
        self.assertRedirects(response, self.factory.get(url, secure=True).build_absolute_uri(url))
        self.assertEqual(submission_original.status, 'invited_to_proposal')
        self.assertEqual(submission_next.status, 'draft_proposal')


class BatchDeterminationTestCase(BaseViewTestCase):
    user_factory = StaffFactory
    url_name = 'funds:submissions:determinations:{}'
    base_view_name = 'batch'

    def dummy_request(self, path):
        request = RequestFactory().get(path)
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()
        request.user = StaffFactory()
        request._messages = FallbackStorage(request)
        return request

    def test_cant_access_without_submissions(self):
        url = self.url(None) + '?action=rejected'
        response = self.client.get(url, follow=True, secure=True)
        self.assertRedirects(response, self.url_from_pattern('apply:submissions:list'))
        self.assertEqual(len(response.context['messages']), 1)

    def test_cant_access_without_action(self):
        submission = ApplicationSubmissionFactory()
        url = self.url(None) + '?submissions=' + str(submission.id)
        response = self.client.get(url, follow=True, secure=True)
        self.assertRedirects(response, self.url_from_pattern('apply:submissions:list'))
        self.assertEqual(len(response.context['messages']), 1)

    def test_can_submit_batch_determination(self):
        submissions = ApplicationSubmissionFactory.create_batch(4)

        url = self.url(None) + '?submissions=' + ','.join([str(submission.id) for submission in submissions]) + '&action=rejected'
        data = {
            'submissions': [submission.id for submission in submissions],
            'data': 'some data',
            'outcome': REJECTED,
            'message': 'Sorry',
            'author': self.user.id,
        }

        response = self.client.post(url, data, secure=True, follow=True)

        for submission in submissions:
            submission = self.refresh(submission)
            self.assertEqual(submission.status, 'rejected')
            self.assertEqual(submission.determinations.count(), 1)

        self.assertRedirects(response, self.url_from_pattern('apply:submissions:list'))

    def test_sets_next_on_redirect(self):
        test_path = '/a/path/?with=query&a=sting'
        request = RequestFactory().get('', PATH_INFO=test_path)
        redirect = BatchDeterminationCreateView.should_redirect(
            request,
            ApplicationSubmission.objects.none(),
            ['rejected'],
        )
        url = urllib.parse.urlparse(redirect.url)
        query = urllib.parse.parse_qs(url.query)
        next_path = urllib.parse.unquote_plus(query['next'][0])
        self.assertEqual(next_path, test_path)

    def test_success_redirects_if_exists(self):
        test_path = '/a/path/?with=query&a=sting'
        view = BatchDeterminationCreateView()
        view.request = self.dummy_request('?next=' + urllib.parse.quote_plus(test_path))
        redirect_url = view.get_success_url()
        self.assertEqual(redirect_url, test_path)

    def test_success_if_no_next(self):
        view = BatchDeterminationCreateView()
        view.request = self.dummy_request('')
        redirect_url = view.get_success_url()
        self.assertEqual(redirect_url, reverse_lazy('apply:submissions:list'))

    def test_message_created_if_determination_exists(self):
        submissions = ApplicationSubmissionFactory.create_batch(2)

        DeterminationFactory(submission=submissions[0], accepted=True, is_draft=False)

        url = self.url(None) + '?submissions=' + ','.join([str(submission.id) for submission in submissions]) + '&action=rejected'
        data = {
            'submissions': [submission.id for submission in submissions],
            'data': 'some data',
            'outcome': REJECTED,
            'message': 'Sorry',
            'author': self.user.id,
        }

        response = self.client.post(url, data, secure=True, follow=True)

        self.assertEqual(submissions[0].determinations.count(), 1)
        self.assertEqual(submissions[0].determinations.first().outcome, ACCEPTED)

        self.assertEqual(submissions[1].determinations.count(), 1)
        self.assertEqual(submissions[1].determinations.first().outcome, REJECTED)

        # 5 base - 2 x django messages, 1 x activity feed, 1 x email, 1 x slack
        # plus 1 extra for unable to determine
        self.assertEqual(len(response.context['messages']), 6)


class UserDeterminationFormTestCase(BaseViewTestCase):
    user_factory = UserFactory
    url_name = 'funds:submissions:determinations:{}'
    base_view_name = 'detail'

    def get_kwargs(self, instance):
        return {'submission_pk': instance.id}

    def test_cant_access_form(self):
        submission = ApplicationSubmissionFactory(status='in_discussion')
        response = self.get_page(submission, 'form')
        self.assertEqual(response.status_code, 403)
