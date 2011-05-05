import unittest
from TestInput import TestInputSingleton
import mc_bin_client
import uuid
import logger
import crc32
from membase.api.rest_client import RestConnection
from membase.helper.bucket_helper import BucketOperationHelper
from membase.helper.cluster_helper import ClusterOperationHelper
from memcached.helper.data_helper import MemcachedClientHelper

class SimpleSetGetTestBase(object):
    log = None
    keys = None
    servers = None
    input = None
    test = None
    bucket_port = None
    bucket_name = None

    def setUp_bucket(self, bucket_name, port, bucket_type, unittest):

        self.log = logger.Logger.get_logger()
        self.input = TestInputSingleton.input
        unittest.assertTrue(self.input, msg="input parameters missing...")
        self.test = unittest
        self.servers = self.input.servers
        self.bucket_port = port
        self.bucket_name = bucket_name
        ClusterOperationHelper.cleanup_cluster(self.servers)
        BucketOperationHelper.delete_all_buckets_or_assert(self.servers, self.test)

        for serverInfo in self.servers:
            rest = RestConnection(serverInfo)
            info = rest.get_nodes_self()
            rest.init_cluster(username = serverInfo.rest_username,
                              password = serverInfo.rest_password)
            rest.init_cluster_memoryQuota(memoryQuota=info.mcdMemoryReserved)
            bucket_ram = info.mcdMemoryReserved * 2 / 3
            if bucket_name != 'default' and self.bucket_port == 11211:
                rest.create_bucket(bucket=bucket_name,
                                   bucketType=bucket_type,
                                   ramQuotaMB=bucket_ram,
                                   replicaNumber=1,
                                   proxyPort=self.bucket_port,
                                   authType='sasl',
                                   saslPassword='password')
                msg = 'create_bucket succeeded but bucket "default" does not exist'
                self.test.assertTrue(BucketOperationHelper.wait_for_bucket_creation(bucket_name, rest), msg=msg)
                BucketOperationHelper.wait_till_memcached_is_ready_or_assert([serverInfo],
                                                                             self.bucket_port,
                                                                             test=unittest,
                                                                             bucket_name=self.bucket_name,
                                                                             bucket_password='password')
            else:
                rest.create_bucket(bucket=bucket_name,
                                   bucketType=bucket_type,
                                   ramQuotaMB=bucket_ram,
                                   replicaNumber=1,
                                   proxyPort=self.bucket_port)
                msg = 'create_bucket succeeded but bucket "default" does not exist'
                self.test.assertTrue(BucketOperationHelper.wait_for_bucket_creation(bucket_name, rest), msg=msg)
                BucketOperationHelper.wait_till_memcached_is_ready_or_assert([serverInfo],
                                                                             self.bucket_port,
                                                                             test=unittest,
                                                                             bucket_name=self.bucket_name)

    #distribution = {10: 0.4, 20: 0.4, 100: 0.2}
    def set_get_test(self,value_size_distribution,number_of_items):
        for serverInfo in self.servers:
            client = MemcachedClientHelper.create_memcached_client(ip=serverInfo.ip,
                                                                   bucket=self.bucket_name,
                                                                   port=self.bucket_port,
                                                                   password='password')
            inserted, rejected = MemcachedClientHelper.load_bucket(serverInfo=serverInfo,
                                                                   name=self.bucket_name,
                                                                   port=self.bucket_port,
                                                                   number_of_items=number_of_items,
                                                                   value_size_distribution=value_size_distribution)

            for key in inserted:
                try:
                    client.vbucketId = crc32.crc32_hash(key) & 1023
                    #value should have only stars ?
                    flag, keyx, value = client.get(key=key)
                    self.test.assertTrue(value.find('*') != -1, 'value mismatch')
                except mc_bin_client.MemcachedError as error:
                    self.log.info('memcachedError : {0}'.format(error.status))
                    self.test.fail("unable to get a pre-inserted key : {0}".format(key))


    def tearDown_bucket(self):
        BucketOperationHelper.delete_all_buckets_or_assert(self.servers, self.test)


class SimpleSetGetMembaseBucketDefaultPort11211(unittest.TestCase):
    simpleSetGetTestBase = None

    def setUp(self):
        self.simpleSetGetTestBase = SimpleSetGetTestBase()
        self.simpleSetGetTestBase.setUp_bucket('default', 11211, 'membase', self)

    def test_set_get_small_keys(self):
        self.simpleSetGetTestBase.set_get_small_keys()

    def test_set_get_large_keys(self):
        self.simpleSetGetTestBase.set_get_large_keys()

    def tearDown(self):
        if self.simpleSetGetTestBase:
            self.simpleSetGetTestBase.tearDown_bucket()


class SimpleSetGetMembaseBucketNonDefaultDedicatedPort(unittest.TestCase):
    simpleSetGetTestBase = None

    def setUp(self):
        self.simpleSetGetTestBase = SimpleSetGetTestBase()
        self.simpleSetGetTestBase.setUp_bucket('setget-{0}'.format(uuid.uuid4()), 11220, 'membase', self)

    def test_set_get_small_keys(self):
        distribution = {10: 0.4, 20: 0.4, 100: 0.2}
        self.simpleSetGetTestBase.set_get_test(distribution,4000)


    def test_set_get_large_keys(self):
        distribution = {100 * 1024: 0.5, 200 * 1024: 0.49, 1 * 1024 * 1024: 0.001}
        self.simpleSetGetTestBase.set_get_test(distribution,4000)


    def tearDown(self):
        if self.simpleSetGetTestBase:
            self.simpleSetGetTestBase.tearDown_bucket()


class SimpleSetGetMembaseBucketNonDefaultPost11211(unittest.TestCase):
    simpleSetGetTestBase = None

    def setUp(self):
        self.simpleSetGetTestBase = SimpleSetGetTestBase()
        self.simpleSetGetTestBase.setUp_bucket('setget-{0}'.format(uuid.uuid4()), 11211, 'membase', self)

    def test_set_get_small_keys(self):
        distribution = {10: 0.4, 20: 0.4, 100: 0.2}
        self.simpleSetGetTestBase.set_get_test(distribution,4000)

    def test_set_get_large_keys(self):
        distribution = {100 * 1024: 0.5, 200 * 1024: 0.49, 1 * 1024 * 1024: 0.001}
        self.simpleSetGetTestBase.set_get_test(distribution,4000)

    def tearDown(self):
        if self.simpleSetGetTestBase:
            self.simpleSetGetTestBase.tearDown_bucket()