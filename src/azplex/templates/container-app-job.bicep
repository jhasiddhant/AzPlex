targetScope = 'resourceGroup'

// ============================================================================
// AZURE CONTAINER APP JOB
// ============================================================================
// This template creates a Container App Job in an existing Container Apps
// Environment. Supports event-driven triggers (e.g., Azure Service Bus) using
// a user-assigned managed identity for ACR pulls and scaler authentication.
//
// Requirements:
// - Existing Container Apps Environment in the same Resource Group
// - Existing User-Assigned Managed Identity with required role assignments
//   (AcrPull on the registry, Service Bus Data Receiver on the namespace, etc.)
// ============================================================================

@description('Name of the Container App Job.')
@minLength(2)
@maxLength(32)
param jobName string

@description('Region for the Container App Job. Should match the Container Apps Environment region.')
param location string

@description('Resource ID of the existing Container Apps Environment.')
param environmentId string

@description('Resource ID of the User-Assigned Managed Identity used for ACR pull and scaler auth.')
param userAssignedIdentityId string

@description('Workload profile name. Use "Consumption" for serverless.')
param workloadProfileName string = 'Consumption'

@description('Trigger type for the job.')
@allowed([
  'Event'
  'Schedule'
  'Manual'
])
param triggerType string = 'Event'

@description('Replica timeout in seconds.')
@minValue(1)
param replicaTimeout int = 28800

@description('Replica retry limit.')
@minValue(0)
param replicaRetryLimit int = 0

@description('Number of replicas to complete successfully for the job to succeed (event trigger).')
@minValue(1)
param replicaCompletionCount int = 1

@description('Number of replicas to run in parallel per execution (event trigger).')
@minValue(1)
param parallelism int = 1

@description('Minimum executions for event-driven scaling.')
@minValue(0)
param minExecutions int = 0

@description('Maximum executions for event-driven scaling.')
@minValue(1)
param maxExecutions int = 5

@description('Polling interval (seconds) for the event-driven scaler.')
@minValue(1)
param pollingInterval int = 20

@description('Container image (full reference, e.g., myregistry.azurecr.io/myimage:tag).')
param containerImage string

@description('Container Registry server (e.g., myregistry.azurecr.io). Empty disables registry config.')
param registryServer string = ''

@description('CPU cores allocated to the container (e.g., 0.5, 1, 2).')
param cpu int = 2

@description('Memory allocated to the container (e.g., 1Gi, 2Gi, 4Gi).')
param memory string = '4Gi'

@description('Environment variables: array of { name, value } or { name, secretRef } objects.')
param envVars array = []

@description('Container command override (array of strings). Empty uses image default.')
param containerCommand array = []

@description('Container args override (array of strings). Empty uses image default.')
param containerArgs array = []

@description('Scaler rules for event-driven jobs (KEDA-compatible). Defaults to empty (no auto-scaling rule).')
param scaleRules array = []

// ============================================================================
// CONTAINER APP JOB
// ============================================================================

resource containerAppJob 'Microsoft.App/jobs@2025-10-02-preview' = {
  name: jobName
  location: location
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    workloadProfileName: workloadProfileName
    configuration: {
      triggerType: triggerType
      replicaTimeout: replicaTimeout
      replicaRetryLimit: replicaRetryLimit
      eventTriggerConfig: triggerType == 'Event' ? {
        replicaCompletionCount: replicaCompletionCount
        parallelism: parallelism
        scale: {
          minExecutions: minExecutions
          maxExecutions: maxExecutions
          pollingInterval: pollingInterval
          rules: scaleRules
        }
      } : null
      registries: empty(registryServer) ? [] : [
        {
          server: registryServer
          identity: userAssignedIdentityId
        }
      ]
      identitySettings: []
    }
    template: {
      containers: [
        {
          image: containerImage
          imageType: 'ContainerImage'
          name: jobName
          command: containerCommand
          args: containerArgs
          env: envVars
          resources: {
            cpu: cpu
            memory: memory
          }
          probes: []
        }
      ]
    }
  }
}

// ============================================================================
// OUTPUTS
// ============================================================================

output jobId string = containerAppJob.id
output jobName string = containerAppJob.name
output principalId string = containerAppJob.identity.principalId
