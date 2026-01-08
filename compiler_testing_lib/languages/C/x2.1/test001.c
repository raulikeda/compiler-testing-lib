// For implementation
n = 5;
y = 1;
i = 0;
for (i = 0; i < n; i = i + 1)
{
  n = n * i;
}
printf(i == n ? y : n);
printf(i == n+1 ? y : n);