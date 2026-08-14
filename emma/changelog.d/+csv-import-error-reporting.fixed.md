A CSV import that failed no longer reports success. Rows rejected by Infrahub are now
counted, and the result names how many of the file's rows were imported. Previously
every row could be rejected and the import still ended with "Loading completed with
success".
