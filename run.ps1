$Pattern = "`".+`", line \d+"

$error_style = "`e[38;2;244;41;45m`e[4m"
$normal_style = "`e[38;2;127;177;249m"

function global:ColorMatch
{
   param(
      [Parameter(ValueFromPipeline = $true)]
      [string] $InputObject
   )

   begin{ $r = [regex]$Pattern }
   process
   {
       $ms = $r.Matches($inputObject)
       $startIndex = 0

       foreach($m in $ms)
       {
          $nonMatchLength = $m.Index - $startIndex
          Write-Host $normal_style$($inputObject.Substring($startIndex, $nonMatchLength)) -NoNew
          Write-Host $error_style$($m.Value) -NoNew
          $startIndex = $m.Index + $m.Length
       }

       if($startIndex -lt $inputObject.Length)
       {
          Write-Host $normal_style$($inputObject.Substring($startIndex)) -NoNew
       }
        Write-Host
   }
}

invoke-expression -Command ".`"$PSScriptRoot\\.venv\\Scripts\\python.exe`" -u `"$PSScriptRoot\\src\\main.py`"  2>&1 |  ColorMatch"