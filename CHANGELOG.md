# alexandrosnt\.certloom Release Notes

**Topics**

- <a href="#v0-1-1">v0\.1\.1</a>
    - <a href="#release-summary">Release Summary</a>
    - <a href="#new-modules">New Modules</a>

<a id="v0-1-1"></a>
## v0\.1\.1

<a id="release-summary"></a>
### Release Summary

First release\. Modules for teams\, probe scopes\, endpoints\, notification channels\, ACME issuers \(with EAB\)\, single\-use EAB keys\, central DNS\-01 solvers\, certificate templates and the monitoring policy\, info modules\, agent enrollment tokens\, and the agent role for Debian and Red Hat family hosts\.

<a id="new-modules"></a>
### New Modules

* alexandrosnt\.certloom\.agent\_enrollment\_token \- Create a one\-time certloom agent enrollment token\.
* alexandrosnt\.certloom\.agent\_info \- List certloom enrolled agents\.
* alexandrosnt\.certloom\.channel \- Manage certloom notification channels\.
* alexandrosnt\.certloom\.dns\_solver \- Manage central certloom DNS\-01 solvers\.
* alexandrosnt\.certloom\.endpoint \- Manage TLS endpoints that certloom probes\.
* alexandrosnt\.certloom\.issuer \- Manage certloom ACME issuers\.
* alexandrosnt\.certloom\.issuer\_eab\_key \- Manage single\-use EAB keys of a certloom issuer\.
* alexandrosnt\.certloom\.issuer\_info \- List certloom ACME issuers\.
* alexandrosnt\.certloom\.policy \- Apply the certloom monitoring policy\.
* alexandrosnt\.certloom\.scope \- Manage certloom probe scopes\.
* alexandrosnt\.certloom\.scope\_info \- List certloom probe scopes\.
* alexandrosnt\.certloom\.team \- Manage certloom teams\.
* alexandrosnt\.certloom\.team\_info \- List certloom teams\.
* alexandrosnt\.certloom\.template \- Manage certloom certificate templates\.
