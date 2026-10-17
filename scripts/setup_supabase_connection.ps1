# Dot-source from the PowerShell session that will run Python. Never save credentials.
& {
    $securePassword = $null
    $plainPassword = $null
    $encodedPassword = $null
    try {
        # Never leave a stale/exposed connection active after cancellation or failure.
        Remove-Item Env:FACTORYMIND_DATABASE_URL -ErrorAction SilentlyContinue
        Write-Host 'Rotate the exposed database password in Supabase before continuing.'
        $securePassword = Read-Host 'Newly rotated Supabase database password (not the old password)' -AsSecureString
        $plainPassword = [System.Net.NetworkCredential]::new('', $securePassword).Password
        if ([string]::IsNullOrEmpty($plainPassword)) { throw 'A newly rotated password is required.' }
        $encodedPassword = [Uri]::EscapeDataString($plainPassword)
        $env:FACTORYMIND_DATABASE_URL = 'postgresql://postgres.qeetbmeleqsmlqywtdyr:' + $encodedPassword + '@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require'
        Write-Host 'FACTORYMIND_DATABASE_URL set for this PowerShell session and child processes.'
        Write-Host 'Scheme: postgresql; Host: aws-0-ap-southeast-1.pooler.supabase.com; Port: 5432'
        Write-Host 'Database: postgres; Username present: True; Password present: True; SSL: require; Pool: session'
        Write-Warning 'Do not commit credentials or print the connection URI. Run the connection test before migration.'
    }
    finally {
        $plainPassword = $null
        $encodedPassword = $null
        if ($null -ne $securePassword) { $securePassword.Dispose() }
        $securePassword = $null
        # .NET strings cannot be reliably zeroed; plaintext references are scoped here.
        Remove-Variable plainPassword, encodedPassword, securePassword -ErrorAction SilentlyContinue
    }
}
