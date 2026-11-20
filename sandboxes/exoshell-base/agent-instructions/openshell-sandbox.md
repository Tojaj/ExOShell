# OpenShell sandbox

You run inside an OpenShell sandbox as the `sandbox` user. The image's policy
is available at `/etc/openshell/policy.yaml`; inspect it when diagnosing
filesystem or network access failures. The running sandbox may have policy
overrides or attached providers, so this file may not show all effective rules.

Network access is default-deny. If access is necessary, ask the user to update
the policy — report binary, host, port, and command.

The user can approve the rule in `openshell term` or apply an ExOShell policy
overlay. Only `network_policies` can be allowed at runtime.
