from clarity_ext.dilution import DilutionScheme
from clarity_ext import UnitConversion
from clarity_ext.repository.file_repository import FileRepository
from clarity_ext.utils import lazyprop
from clarity_ext import ClaritySession
from clarity_ext.service import ArtifactService, FileService, StepLoggerService
from clarity_ext.repository import StepRepository
from clarity_ext import utils
from clarity_ext.driverfile import OSService
from clarity_ext.service.validation_service import ERRORS_AND_WARNING_ENTRY_NAME
from clarity_ext.domain.udf import Udf


class ExtensionContext(Udf):
    """
    Defines context objects for extensions.


    Details: The context provides simplified access to underlying
    services, so the extension writer writes minimal code and is
    limited by default to only a subset of functionality, while being
    able to access the underlying services if needed.
    """

    def __init__(self, session, artifact_service, file_service, current_user, step_logger_service, step_repo,
                 cache=False):
        """
        Initializes the context.

        :param session: An object encapsulating the connection to Clarity
        :param artifact_service: Provides access to artifacts in the current step
        :param file_service: Provides access to result files locally on the machine.
        :param step_logger_service: Provides access to logging via the context.
        :param step_repo: The repository for the current step
        :param cache: Set to True to use the cache folder (.cache) for downloaded files
        """
        super(ExtensionContext, self).__init__(
            api_resource=session.current_step, id=session.current_step_id)
        self.session = session
        self.cache = cache
        self.logger = step_logger_service
        self.units = UnitConversion()
        self._update_queue = []
        self.current_step = session.current_step
        self.artifact_service = artifact_service
        self.file_service = file_service
        self.current_user = current_user
        self.step_repo = step_repo
        self.response = None
        self.dilution_scheme = None

    @staticmethod
    def create(step_id, cache=False):
        """
        Creates a context with all required services set up. This is the way
        a context is meant to be created in production and integration tests,
        use the constructor for custom use and unit tests.
        """
        session = ClaritySession.create(step_id)
        step_repo = StepRepository(session)
        artifact_service = ArtifactService(step_repo)
        current_user = step_repo.current_user()
        file_repository = FileRepository(session)
        file_service = FileService(artifact_service, file_repository, False, OSService())
        step_logger_service = StepLoggerService("Step log", file_service)
        return ExtensionContext(session, artifact_service, file_service, current_user, step_logger_service, step_repo,
                                cache=cache)

    @property
    def udfs(self):
        return self.step_repo.all_udfs()

    def init_dilution_scheme(self, concentration_ref=None, include_blanks=False):
        file_list = [file for file in self.shared_files if file.name ==
                     ERRORS_AND_WARNING_ENTRY_NAME]
        if not len(file_list) == 1:
            raise ValueError("This step is not configured with the shared file entry for {}".format(
                ERRORS_AND_WARNING_ENTRY_NAME))
        error_log_artifact = file_list[0]
        # TODO: The caller needs to provide the robot
        self.dilution_scheme = DilutionScheme(
            self.artifact_service, "Hamilton", concentration_ref=concentration_ref,
            include_blanks=include_blanks, error_log_artifact=error_log_artifact)

    @lazyprop
    def shared_files(self):
        """
        Fetches all share files for the current step
        """
        return self.artifact_service.shared_files()

    @lazyprop
    def all_analytes(self):
        return self.artifact_service.all_analyte_pairs()

    @lazyprop
    def output_containers(self):
        """
        Returns all output containers, with respective items
        """
        # TODO: Ensure that the artifacts are not fetched again
        return self.artifact_service.all_output_containers()

    @lazyprop
    def output_container(self):
        """
        A convenience method for fetching a single output container and raising
        an exception if there is more than one.
        """
        return utils.single(self.artifact_service.all_output_containers())

    @lazyprop
    def input_containers(self):
        """
        Returns a list with all input containers, where each container has been extended with the attribute
        `artifacts`, containing all artifacts in the container
        """
        return self.artifact_service.all_input_containers()

    @lazyprop
    def input_container(self):
        """
        A convenience method for fetching a single input container and raising
        an exception if there is more than one.
        """
        return utils.single(self.artifact_service.all_input_containers())

    def cleanup(self):
        """Cleans up any downloaded resources. This method will be automatically
        called by the framework and does not need to be called by extensions"""
        # Clean up:
        self.file_service.cleanup()

    def local_shared_file(self, name, mode="r", is_xml=False):
        f = self.file_service.local_shared_file(name, mode=mode)
        if is_xml:
            return self.file_service.parse_xml(f)
        else:
            return f

    def output_result_file_by_id(self, file_id):
        """Returns the output result file by id"""
        return self.artifact_service.output_file_by_id(file_id)

    @property
    def output_result_files(self):
        return self.artifact_service.all_output_files()

    @property
    def pid(self):
        return self.session.current_step_id

    def update(self, obj):
        """Add an object that has a commit method to the list of objects to update"""
        self._update_queue.append(obj)

    def commit(self):
        """Commits all objects that have been added via the update method, using batch processing if possible"""
        self.response = self.artifact_service.update_artifacts(self._update_queue)

