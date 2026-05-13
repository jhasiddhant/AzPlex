targetScope = 'resourceGroup'

@description('Service Bus namespace name (globally unique, 6-50 alphanumeric/hyphen).')
@minLength(6)
@maxLength(50)
param serviceBusNamespaceName string

@description('Region for the Service Bus namespace.')
param location string

@description('SKU tier for the Service Bus namespace.')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param skuName string = 'Basic'

@description('Number of messaging partitions (Premium only). Use 0 for Basic/Standard.')
@minValue(0)
param premiumMessagingPartitions int = 0

@description('Minimum TLS version.')
@allowed([
  '1.0'
  '1.1'
  '1.2'
])
param minimumTlsVersion string = '1.2'

@description('Enable public network access.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

@description('Disable local (SAS key) authentication. True enforces Entra ID auth only.')
param disableLocalAuth bool = true

@description('Enable zone redundancy (Standard/Premium only).')
param zoneRedundant bool = true

@description('Default action for the network rule set when public access is enabled.')
@allowed([
  'Allow'
  'Deny'
])
param networkRuleSetDefaultAction string = 'Allow'

@description('Allow trusted Microsoft services to bypass network rules.')
param trustedServiceAccessEnabled bool = false

@description('Queues to create under the namespace. Provide an array of queue config objects.')
param queues array = []

// Service Bus namespace
resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2025-05-01-preview' = {
  name: serviceBusNamespaceName
  location: location
  sku: {
    name: skuName
    tier: skuName
  }
  properties: {
    platformCapabilities: {
      confidentialCompute: {
        mode: 'Disabled'
      }
    }
    geoDataReplication: {
      maxReplicationLagDurationInSeconds: 0
      locations: [
        {
          locationName: location
          roleType: 'Primary'
        }
      ]
    }
    premiumMessagingPartitions: premiumMessagingPartitions
    minimumTlsVersion: minimumTlsVersion
    publicNetworkAccess: publicNetworkAccess
    disableLocalAuth: disableLocalAuth
    zoneRedundant: zoneRedundant
  }
}

// Root manage shared access key (created by default by Azure; declared for explicit management)
resource rootManageSharedAccessKey 'Microsoft.ServiceBus/namespaces/authorizationrules@2025-05-01-preview' = {
  parent: serviceBusNamespace
  name: 'RootManageSharedAccessKey'
  properties: {
    rights: [
      'Listen'
      'Manage'
      'Send'
    ]
  }
}

// Default network rule set
resource networkRuleSet 'Microsoft.ServiceBus/namespaces/networkrulesets@2025-05-01-preview' = {
  parent: serviceBusNamespace
  name: 'default'
  properties: {
    publicNetworkAccess: publicNetworkAccess
    defaultAction: networkRuleSetDefaultAction
    virtualNetworkRules: []
    ipRules: []
    trustedServiceAccessEnabled: trustedServiceAccessEnabled
  }
}

// Queues
resource serviceBusQueues 'Microsoft.ServiceBus/namespaces/queues@2025-05-01-preview' = [for queue in queues: {
  parent: serviceBusNamespace
  name: queue.name
  properties: {
    maxMessageSizeInKilobytes: contains(queue, 'maxMessageSizeInKilobytes') ? queue.maxMessageSizeInKilobytes : 256
    lockDuration: contains(queue, 'lockDuration') ? queue.lockDuration : 'PT5M'
    maxSizeInMegabytes: contains(queue, 'maxSizeInMegabytes') ? queue.maxSizeInMegabytes : 1024
    requiresDuplicateDetection: contains(queue, 'requiresDuplicateDetection') ? queue.requiresDuplicateDetection : false
    requiresSession: contains(queue, 'requiresSession') ? queue.requiresSession : false
    defaultMessageTimeToLive: contains(queue, 'defaultMessageTimeToLive') ? queue.defaultMessageTimeToLive : 'P14D'
    deadLetteringOnMessageExpiration: contains(queue, 'deadLetteringOnMessageExpiration') ? queue.deadLetteringOnMessageExpiration : false
    enableBatchedOperations: contains(queue, 'enableBatchedOperations') ? queue.enableBatchedOperations : true
    duplicateDetectionHistoryTimeWindow: contains(queue, 'duplicateDetectionHistoryTimeWindow') ? queue.duplicateDetectionHistoryTimeWindow : 'PT10M'
    maxDeliveryCount: contains(queue, 'maxDeliveryCount') ? queue.maxDeliveryCount : 10
    status: contains(queue, 'status') ? queue.status : 'Active'
    autoDeleteOnIdle: contains(queue, 'autoDeleteOnIdle') ? queue.autoDeleteOnIdle : 'P10675199DT2H48M5.4775807S'
    enablePartitioning: contains(queue, 'enablePartitioning') ? queue.enablePartitioning : false
    enableExpress: contains(queue, 'enableExpress') ? queue.enableExpress : false
  }
}]

output serviceBusNamespaceId string = serviceBusNamespace.id
output serviceBusNamespaceName string = serviceBusNamespace.name
output serviceBusEndpoint string = serviceBusNamespace.properties.serviceBusEndpoint
output queueNames array = [for (queue, i) in queues: serviceBusQueues[i].name]
