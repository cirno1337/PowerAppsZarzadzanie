<#
.SYNOPSIS
    Provisions the Applications, DocumentationJobs, DocumentationVersions,
    and Configuration lists, plus the PowerPlatformDocumentation library,
    on a SharePoint Online site — using the PnP.PowerShell module.

.DESCRIPTION
    REQUIRES CORPORATE ACCESS. This script has NOT been run or validated
    against a real SharePoint Online tenant — there is none available while
    developing offline. It is written against the documented,
    officially-supported PnP.PowerShell cmdlets (see
    https://pnp.github.io/powershell/), but treat it as a reviewed DRAFT:
    read it fully, run it against a non-production/test site first, and
    adjust field types if PnP's behavior differs from what's assumed here.

    Column definitions are read from sharepoint/lists/*.json (kept as the
    single source of truth — see sharepoint/README.md) so this script and
    the documentation can't silently drift apart.

.PARAMETER SiteUrl
    The SharePoint Online site URL. REQUIRES TENANT CONFIGURATION — never
    hard-code this; pass it explicitly every time.

.EXAMPLE
    ./provision-lists.ps1 -SiteUrl "https://<tenant>.sharepoint.com/sites/<site>"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$SiteUrl
)

$ErrorActionPreference = "Stop"

# Install-Module PnP.PowerShell -Scope CurrentUser   # if not already installed
Import-Module PnP.PowerShell -ErrorAction Stop

Write-Host "Connecting to $SiteUrl ..."
Connect-PnPOnline -Url $SiteUrl -Interactive

$listsDir = Join-Path $PSScriptRoot "../lists"

function New-ListFromDefinition {
    param([string]$DefinitionPath)

    $definition = Get-Content $DefinitionPath -Raw | ConvertFrom-Json
    $listName = $definition.listName

    if (Get-PnPList -Identity $listName -ErrorAction SilentlyContinue) {
        Write-Host "List '$listName' already exists — skipping creation, only adding missing columns."
    } else {
        Write-Host "Creating list '$listName' ..."
        New-PnPList -Title $listName -Template GenericList | Out-Null
    }

    foreach ($column in $definition.columns) {
        if ($column.name -in @("Title", "ID", "Created", "Modified", "Author", "Editor")) {
            continue  # built-in columns, nothing to create
        }
        if (Get-PnPField -List $listName -Identity $column.name -ErrorAction SilentlyContinue) {
            continue
        }

        Write-Host "  Adding column '$($column.name)' ($($column.type)) to '$listName' ..."
        switch ($column.type) {
            "Single line of text" {
                Add-PnPField -List $listName -DisplayName $column.name -InternalName $column.name -Type Text
            }
            "Multiple lines of text" {
                Add-PnPField -List $listName -DisplayName $column.name -InternalName $column.name -Type Note
            }
            "Number" {
                Add-PnPField -List $listName -DisplayName $column.name -InternalName $column.name -Type Number
            }
            "Yes/No" {
                Add-PnPField -List $listName -DisplayName $column.name -InternalName $column.name -Type Boolean
            }
            "Date and Time" {
                Add-PnPField -List $listName -DisplayName $column.name -InternalName $column.name -Type DateTime
            }
            "Person or Group" {
                Add-PnPField -List $listName -DisplayName $column.name -InternalName $column.name -Type User
            }
            "Hyperlink or Picture" {
                Add-PnPField -List $listName -DisplayName $column.name -InternalName $column.name -Type URL
            }
            "Choice" {
                Add-PnPField -List $listName -DisplayName $column.name -InternalName $column.name -Type Choice -Choices $column.choices
            }
            "Lookup" {
                # REQUIRES CORPORATE ACCESS to verify: Add-PnPField's Lookup
                # support needs the target list's GUID, resolved here at
                # provisioning time rather than hard-coded.
                $targetList = Get-PnPList -Identity $column.lookupList
                Add-PnPField -List $listName -DisplayName $column.name -InternalName $column.name `
                    -Type Lookup -LookupList $targetList.Id -LookupField $column.lookupField
            }
            default {
                Write-Warning "  Unhandled column type '$($column.type)' for '$($column.name)' — add manually."
            }
        }
    }
}

foreach ($file in @("Applications.json", "DocumentationJobs.json", "DocumentationVersions.json", "Configuration.json")) {
    New-ListFromDefinition -DefinitionPath (Join-Path $listsDir $file)
}

$libraryName = "PowerPlatformDocumentation"
if (-not (Get-PnPList -Identity $libraryName -ErrorAction SilentlyContinue)) {
    Write-Host "Creating document library '$libraryName' ..."
    New-PnPList -Title $libraryName -Template DocumentLibrary | Out-Null
}
foreach ($folder in @("_jobs", "_templates", "_logs")) {
    Resolve-PnPFolder -SiteRelativePath "$libraryName/$folder" | Out-Null
}

Write-Host "Done. Review permissions per SECURITY.md before granting the worker's service account access."
