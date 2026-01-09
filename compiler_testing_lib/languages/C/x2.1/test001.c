// For implementation
n = 5;
y = 1;
i = 0;
for (i = 0; i < n; i = i + 1)
{
  y = y * (i + 1);
}
printf(i == n ? y : n);
printf(i == n+1 ? y : n);