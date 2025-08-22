Attribute VB_Name = "Module1"

' **************************************************************************************************
' ** MODULE 1 - VERSION FINALE AVEC GESTION UTF-8 **
' **************************************************************************************************

' ==================================================================================================
' == CONFIGURATION DU SERVEUR ==
' ==================================================================================================
' *** ADRESSE IP MISE À JOUR ***
Public Const SERVER_BASE_URL As String = "https://sanouchat-excelcivil.hf.space"

' Variable globale pour la cellule active
Public ActiveTargetCell As Range

' ==================================================================================================
' == PROCÉDURE PRINCIPALE ==
' ==================================================================================================
Public Sub ShowSearchSuggestions(TargetCell As Range)
    Dim suggestions As Collection
    Dim libraryName As String
    Dim priceType As String
    Dim isFormLoaded As Boolean
    Dim frm As Object
    
    Set ActiveTargetCell = TargetCell
    
    isFormLoaded = False
    For Each frm In VBA.UserForms
        If frm.Name = "UserForm1" Then
            isFormLoaded = True
            Exit For
        End If
    Next frm

    If Not isFormLoaded Then
        MsgBox "Veuillez d'abord afficher la boîte à outils pour sélectionner une bibliothèque.", vbInformation, "Boîte à Outils Fermée"
        Exit Sub
    End If
    
    Load LoadingForm
    With LoadingForm
        .StartUpPosition = 0
        .Left = Application.Left + (Application.Width / 2) - (.Width / 2)
        .Top = Application.Top + (Application.Height / 2) - (.Height / 2)
        .Show vbModeless
    End With
    DoEvents
    
    libraryName = UserForm1.Biblio.text
    priceType = UserForm1.GetSelectedPriceType()
    
    If libraryName = "" Then
        MsgBox "Veuillez sélectionner une bibliothèque dans la boîte à outils.", vbExclamation, "Bibliothèque non sélectionnée"
        GoTo Cleanup
    End If
    
    Set suggestions = GetSuggestionsFromAPI(TargetCell.value, libraryName, priceType)
    
    If suggestions Is Nothing Or suggestions.Count = 0 Then
        On Error Resume Next
        SearchForm.Hide
        On Error GoTo 0
        GoTo Cleanup
    End If
    
    Load SearchForm
    SearchForm.lstResults.Clear
    
    Dim i As Integer
    For i = 1 To suggestions.Count
        Dim suggestion As Object
        Set suggestion = suggestions(i)
        SearchForm.lstResults.AddItem suggestion("designation") & " | " & suggestion("unite") & " | " & suggestion("prix") & " | Score: " & suggestion("score")
    Next i
    
    SearchForm.Caption = "Résultats pour '" & TargetCell.value & "'"
    
    With SearchForm
        .StartUpPosition = 0
        .Left = Application.Left + ActiveTargetCell.Left + 250
        .Top = Application.Top + ActiveTargetCell.Top + ActiveTargetCell.Height + 100
        .Show vbModeless
    End With
    
Cleanup:
    Unload LoadingForm
    Exit Sub
    
End Sub

' ==================================================================================================
' == FONCTIONS DE COMMUNICATION API (AVEC CORRECTION UTF-8) ==
' ==================================================================================================
Private Function GetSuggestionsFromAPI(query As String, libraryName As String, priceType As String) As Collection
    Dim http As Object
    Dim url As String
    Dim decodedResponse As String
    
    url = SERVER_BASE_URL & "/search?q=" & WorksheetFunction.EncodeURL(query)
    url = url & "&library=" & WorksheetFunction.EncodeURL(libraryName)
    url = url & "&price_type=" & WorksheetFunction.EncodeURL(priceType)
    
    Set http = CreateObject("MSXML2.XMLHTTP.6.0")
    
    On Error GoTo ErrorHandler
    
    http.Open "GET", url, False
    http.send
    
    If http.Status = 200 Then
        Dim stream As Object
        Set stream = CreateObject("ADODB.Stream")
        stream.Open
        stream.Type = 1 ' adTypeBinary
        stream.Write http.responseBody
        stream.Position = 0
        stream.Type = 2 ' adTypeText
        stream.Charset = "UTF-8"
        decodedResponse = stream.ReadText
        stream.Close
        Set stream = Nothing
        
        Set GetSuggestionsFromAPI = ParseJsonManually(decodedResponse)
    Else
        Debug.Print "Erreur API: " & http.Status & " - " & http.statusText
        Set GetSuggestionsFromAPI = Nothing
    End If
    
    Set http = Nothing
    Exit Function
    
ErrorHandler:
    Debug.Print "Erreur VBA lors de l'appel API: " & Err.Description
    Set GetSuggestionsFromAPI = Nothing
    Set http = Nothing
End Function

' ==================================================================================================
' == PARSEUR JSON MANUEL ET OPTIMISÉ (Inchangé) ==
' ==================================================================================================
Private Function ParseJsonManually(jsonText As String) As Collection
    Dim suggestions As New Collection
    Dim currentPos As Long, startPos As Long, endPos As Long
    
    On Error GoTo ParseError
    
    currentPos = 1
    Do
        startPos = InStr(currentPos, jsonText, "{")
        If startPos = 0 Then Exit Do
        endPos = InStr(startPos, jsonText, "}")
        If endPos = 0 Then Exit Do
        
        Dim objectStr As String
        objectStr = Mid(jsonText, startPos, endPos - startPos + 1)
        
        Dim dict As Object
        Set dict = CreateObject("Scripting.Dictionary")
        
        dict("designation") = ExtractValue(objectStr, "designation")
        dict("prix") = ExtractValue(objectStr, "prix")
        dict("unite") = ExtractValue(objectStr, "unite")
        dict("score") = ExtractValue(objectStr, "score")
        dict("match_type") = ExtractValue(objectStr, "match_type")
        
        suggestions.Add dict
        currentPos = endPos + 1
    Loop
    
    Set ParseJsonManually = suggestions
    Exit Function

ParseError:
    Debug.Print "Erreur de parsing JSON manuel: " & Err.Description
    Set ParseJsonManually = Nothing
End Function

Private Function ExtractValue(objectStr As String, key As String) As String
    Dim keyPattern As String, value As String
    Dim startPos As Long, endPos As Long
    
    keyPattern = """" & key & """:"
    startPos = InStr(1, objectStr, keyPattern)
    
    If startPos = 0 Then
        ExtractValue = ""
        Exit Function
    End If
    
    startPos = startPos + Len(keyPattern)
    objectStr = Mid(objectStr, startPos)
    objectStr = Trim(objectStr)
    
    If Left(objectStr, 1) = """" Then
        endPos = InStr(2, objectStr, """")
        If endPos > 0 Then value = Mid(objectStr, 2, endPos - 2)
    Else
        endPos = InStr(1, objectStr, ",")
        If endPos = 0 Then
            Dim bracePos As Long
            bracePos = InStr(1, objectStr, "}")
            If bracePos > 0 Then value = Left(objectStr, bracePos - 1) Else value = objectStr
        Else
            value = Left(objectStr, endPos - 1)
        End If
    End If
    
    ExtractValue = Trim(value)
End Function

