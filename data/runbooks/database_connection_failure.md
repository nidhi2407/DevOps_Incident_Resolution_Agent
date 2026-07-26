# Database Connection Failure Troubleshooting

## Symptoms
Application logs show database connection failed, could not connect to database, timeout connecting to database, authentication failed, password authentication failed, unknown database, database does not exist, or migration failed.

## Root Cause
The application cannot connect to its database dependency. Common causes are wrong database hostname, DNS failure, wrong port, database pod down, Service has no endpoints, network policy denial, invalid credentials, missing Secret, or database schema/migration failure.

## Resolution Steps
1. Identify database host, port, database name, and error type from the logs.
2. Check the database Service and endpoints:
   kubectl get svc <db-service> -n <namespace>
   kubectl get endpoints <db-service> -n <namespace>
3. Check database pods and logs:
   kubectl get pods -n <namespace> -l app=<db-label>
   kubectl logs <db-pod> -n <namespace> --tail=100
4. Verify the application Secret or environment variables:
   kubectl describe pod <app-pod> -n <namespace>
   kubectl get secret <db-secret> -n <namespace>
5. Test connectivity from a debug pod or the application pod:
   kubectl exec -n <namespace> <app-pod> -- nc -vz <db-host> <db-port>
6. Fix DNS, Service, credentials, network policy, database availability, or migration state, then restart the app:
   kubectl rollout restart deployment <deployment-name> -n <namespace>
