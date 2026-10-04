# OpenShell sandbox

You run inside an OpenShell sandbox as the `sandbox` user. The image's policy
is available at `/etc/openshell/policy.yaml`; inspect it when diagnosing
filesystem or network access failures. The running sandbox may have policy
overrides or attached providers, so this file may not show all effective rules.
