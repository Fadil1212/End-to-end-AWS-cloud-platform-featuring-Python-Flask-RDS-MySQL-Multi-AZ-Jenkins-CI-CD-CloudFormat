import jenkins.model.Jenkins
import hudson.security.*
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition
import hudson.plugins.git.*
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.domains.Domain
import com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey

def j = Jenkins.get()
def realm = new HudsonPrivateSecurityRealm(false)
realm.createAccount('workshop_admin', new File('/run/workshop/admin-password').text.trim())
j.setSecurityRealm(realm)
def auth = new FullControlOnceLoggedInAuthorizationStrategy()
auth.setAllowAnonymousRead(false)
j.setAuthorizationStrategy(auth)
j.setNumExecutors(1)
j.setSystemMessage('NSRL MySQL Cloud Computing Workshop — GitHub, Jenkins, S3, Multi-AZ RDS, DR & EC2 Python Web App')

def store = SystemCredentialsProvider.getInstance().getStore()
if (!SystemCredentialsProvider.getInstance().getCredentials().any { it.id == 'github-nsrl-readonly' }) {
  def key = new BasicSSHUserPrivateKey(
    CredentialsScope.GLOBAL,
    'github-nsrl-readonly',
    'git',
    new BasicSSHUserPrivateKey.DirectEntryPrivateKeySource(new File('/run/workshop/deploy-key').text),
    '',
    'Read-only deploy key for the NSRL MySQL Cloud Web App repository'
  )
  store.addCredentials(Domain.global(), key)
}

def jobName = System.getenv('JENKINS_JOB_NAME') ?: 'nsrl-mysql-cloud-webapp-delivery'
if (j.getItem(jobName) == null) {
  def job = j.createProject(WorkflowJob, jobName)
  def repoUrl = System.getenv('WORKSHOP_REPO')
  def credId = repoUrl.startsWith('git@') ? 'github-nsrl-readonly' : ''
  def remote = new UserRemoteConfig(repoUrl, '', '', credId)
  def scm = new GitSCM([remote], [new BranchSpec('*/main')], false, [], null, null, [])
  job.setDefinition(new CpsScmFlowDefinition(scm, 'Jenkinsfile'))
  job.save()
}
j.save()
