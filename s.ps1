param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$msg
)
& "$PSScriptRoot\save.ps1" @msg
